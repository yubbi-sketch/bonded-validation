"""exp1의 세 경쟁 모델 — 파라미터 예산을 비슷하게 맞춘 3파전.

  1) TransformerClassifier : 종단(자연어→True/False), 셀프어텐션 O(N^2)
  2) SSMClassifier         : 종단(자연어→True/False), 선형 스캔 O(N)
  3) Extractor             : 문장→(from, to, neg) 슬롯 추출 → 기호 검증기가 판정
"""
import numpy as np
from autograd import T, embedding


def _p(rng, *shape, scale=None):
    scale = scale if scale is not None else 1.0 / np.sqrt(shape[0])
    return T(rng.normal(size=shape) * scale)


def rmsnorm(x, g):
    ms = (x * x).mean(axis=-1, keepdims=True)
    return x * (ms + 1e-6).pow_const(-0.5) * g


class TransformerClassifier:
    """임베딩 + 학습 위치벡터 + 2블록 단일헤드 어텐션 + 평균풀 + 선형."""

    def __init__(self, vocab, d=48, T_len=64, blocks=2, seed=0):
        rng = np.random.default_rng(seed)
        self.d, self.T_len = d, T_len
        self.E = _p(rng, vocab, d, scale=0.08)
        self.P = _p(rng, T_len, d, scale=0.02)
        self.blk = []
        for _ in range(blocks):
            self.blk.append({
                "Wq": _p(rng, d, d), "Wk": _p(rng, d, d), "Wv": _p(rng, d, d),
                "Wo": _p(rng, d, d),
                "W1": _p(rng, d, 2 * d), "W2": _p(rng, 2 * d, d),
                "g1": T(np.ones(d)), "g2": T(np.ones(d)),
            })
        self.Wout = _p(rng, d, 2)

    def params(self):
        ps = [self.E, self.P, self.Wout]
        for b in self.blk:
            ps += list(b.values())
        return ps

    def forward(self, ids):  # ids: (B, T)
        x = embedding(self.E, ids) + self.P  # (B,T,d)
        scale = 1.0 / np.sqrt(self.d)
        for b in self.blk:
            h = rmsnorm(x, b["g1"])
            q, k, v = h.matmul(b["Wq"]), h.matmul(b["Wk"]), h.matmul(b["Wv"])
            att = q.matmul(k.transpose_last()) * scale  # (B,T,T) ← O(N^2) 지점
            att = att.softmax_last()
            x = x + att.matmul(v).matmul(b["Wo"])
            h2 = rmsnorm(x, b["g2"])
            x = x + h2.matmul(b["W1"]).relu().matmul(b["W2"])
        pooled = x.mean(axis=1)  # (B,d)
        return pooled.matmul(self.Wout)


class SSMClassifier:
    """임베딩 + 2층 대각 선형 재귀 스캔(h_t = a⊙h_{t-1} + b⊙x_t) + 게이트 MLP."""

    def __init__(self, vocab, d=48, layers=2, seed=0):
        rng = np.random.default_rng(seed + 100)
        self.d = d
        self.E = _p(rng, vocab, d, scale=0.08)
        self.lyr = []
        for _ in range(layers):
            self.lyr.append({
                "a_raw": T(rng.normal(size=d) * 0.5 + 1.5),  # sigmoid→(0,1) 상태 유지율
                "b": T(np.ones(d) * 0.5),
                "Win": _p(rng, d, d),
                "Wg": _p(rng, d, d),
                "g": T(np.ones(d)),
            })
        self.W1 = _p(rng, d, 2 * d)
        self.W2 = _p(rng, 2 * d, 2)

    def params(self):
        ps = [self.E, self.W1, self.W2]
        for l in self.lyr:
            ps += list(l.values())
        return ps

    def forward(self, ids):  # ids: (B, T)
        B, T_len = ids.shape
        x = embedding(self.E, ids)  # (B,T,d)
        for l in self.lyr:
            a = l["a_raw"].sigmoid()
            u = rmsnorm(x, l["g"]).matmul(l["Win"])
            h = T(np.zeros((B, self.d)), requires_grad=False)
            outs = []
            for t in range(T_len):
                # NumPy 슬라이스는 그래프 밖 — 스텝 입력을 개별 텐서로 취급
                xt = _slice_t(u, t)
                h = h * a + xt * l["b"]
                outs.append(h)
            # 게이트 잔차: x + gate(h_t) — 마지막 상태만 다음 층 풀링에 사용해도 되지만
            # 토큰별 출력 유지 위해 스택
            x = _stack_t(outs) .matmul(l["Wg"]).tanh() + x
        last = x.mean(axis=1)
        return last.matmul(self.W1).relu().matmul(self.W2)


def _slice_t(x, t):
    out = T(x.d[:, t, :], (x,))

    def back():
        g = np.zeros_like(x.d)
        g[:, t, :] = out.grad
        x._accum(g)
    out._back = back
    return out


def _stack_t(tensors):
    data = np.stack([t.d for t in tensors], axis=1)  # (B,T,d)
    out = T(data, tuple(tensors))

    def back():
        for i, t in enumerate(tensors):
            t._accum(out.grad[:, i, :])
    out._back = back
    return out


class Extractor:
    """문장 하나 → (from 엔티티, to 엔티티, 부정 여부) 3개 헤드.

    인코더는 SSM 스캔(경량·O(N)) 공유, 헤드는 엔티티 사전 위 소프트맥스.
    이 모델이 '우리 AI' — 검증기는 이 출력만 믿는다.
    """

    def __init__(self, vocab, n_ent, d=48, seed=0):
        rng = np.random.default_rng(seed + 200)
        self.d = d
        self.E = _p(rng, vocab, d, scale=0.08)
        self.a_raw = T(rng.normal(size=d) * 0.5 + 1.5)
        self.b = T(np.ones(d) * 0.5)
        self.Win = _p(rng, d, d)
        self.g = T(np.ones(d))
        self.Wm = _p(rng, d, d)   # 평균 상태 경로
        self.Wl = _p(rng, d, d)   # 정방향 마지막 상태 경로 (어순 정보)
        self.a2_raw = T(rng.normal(size=d) * 0.5 + 1.5)  # 역방향 스캔 (여전히 O(N))
        self.b2 = T(np.ones(d) * 0.5)
        self.Wl2 = _p(rng, d, d)  # 역방향 마지막 상태 경로
        self.Wfrom = _p(rng, d, n_ent)
        self.Wto = _p(rng, d, n_ent)
        self.Wneg = _p(rng, d, 2)

    def params(self):
        return [self.E, self.a_raw, self.b, self.Win, self.g, self.Wm, self.Wl,
                self.a2_raw, self.b2, self.Wl2,
                self.Wfrom, self.Wto, self.Wneg]

    def forward(self, ids):  # ids: (B, T_sent)
        B, T_len = ids.shape
        x = embedding(self.E, ids)
        u = rmsnorm(x, self.g).matmul(self.Win)
        a = self.a_raw.sigmoid()
        h = T(np.zeros((B, self.d)), requires_grad=False)
        acc = T(np.zeros((B, self.d)), requires_grad=False)
        for t in range(T_len):
            h = h * a + _slice_t(u, t) * self.b
            acc = acc + h
        a2 = self.a2_raw.sigmoid()
        h2 = T(np.zeros((B, self.d)), requires_grad=False)
        for t in range(T_len - 1, -1, -1):
            h2 = h2 * a2 + _slice_t(u, t) * self.b2
        enc = ((acc * (1.0 / T_len)).matmul(self.Wm) + h.matmul(self.Wl)
               + h2.matmul(self.Wl2)).tanh()
        return enc.matmul(self.Wfrom), enc.matmul(self.Wto), enc.matmul(self.Wneg)


def count_params(model):
    return sum(int(np.prod(p.d.shape)) for p in model.params())
