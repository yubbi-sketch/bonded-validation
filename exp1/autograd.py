"""미니 자동미분 엔진 (순수 NumPy) — exp1 전용.

의존성 0 원칙: G3(외부 재현) 게이트를 위해 표준 파이썬 + NumPy만 사용한다.
지원 연산은 exp1의 세 모델(트랜스포머·SSM·추출기)에 필요한 최소 집합.
"""
import numpy as np


class T:
    """추적되는 텐서. d=값, grad=기울기, _back=역전파 클로저."""

    def __init__(self, data, parents=(), back=None, requires_grad=True):
        self.d = np.asarray(data, dtype=np.float64)
        self.grad = None
        self._parents = parents
        self._back = back
        self.requires_grad = requires_grad

    @property
    def shape(self):
        return self.d.shape

    def _accum(self, g):
        if self.grad is None:
            self.grad = np.zeros_like(self.d)
        self.grad += g

    def backward(self):
        topo, seen = [], set()

        def build(t):
            if id(t) in seen or not isinstance(t, T):
                return
            seen.add(id(t))
            for p in t._parents:
                build(p)
            topo.append(t)

        build(self)
        self.grad = np.ones_like(self.d)
        for t in reversed(topo):
            if t._back is not None:
                t._back()

    # ---- 기본 연산 ----
    def __add__(self, o):
        o = o if isinstance(o, T) else T(o, requires_grad=False)
        out = T(self.d + o.d, (self, o))

        def back():
            self._accum(_unbroadcast(out.grad, self.d.shape))
            o._accum(_unbroadcast(out.grad, o.d.shape))
        out._back = back
        return out

    def __mul__(self, o):
        o = o if isinstance(o, T) else T(o, requires_grad=False)
        out = T(self.d * o.d, (self, o))

        def back():
            self._accum(_unbroadcast(out.grad * o.d, self.d.shape))
            o._accum(_unbroadcast(out.grad * self.d, o.d.shape))
        out._back = back
        return out

    def __neg__(self):
        return self * (-1.0)

    def __sub__(self, o):
        return self + (-(o if isinstance(o, T) else T(o, requires_grad=False)))

    def pow_const(self, p):
        out = T(self.d ** p, (self,))

        def back():
            self._accum(out.grad * p * (self.d ** (p - 1)))
        out._back = back
        return out

    def matmul(self, o):
        out = T(self.d @ o.d, (self, o))

        def back():
            ga = out.grad @ np.swapaxes(o.d, -1, -2)
            gb = np.swapaxes(self.d, -1, -2) @ out.grad
            self._accum(_unbroadcast(ga, self.d.shape))
            o._accum(_unbroadcast(gb, o.d.shape))
        out._back = back
        return out

    def transpose_last(self):
        out = T(np.swapaxes(self.d, -1, -2), (self,))

        def back():
            self._accum(np.swapaxes(out.grad, -1, -2))
        out._back = back
        return out

    def sum(self, axis=None, keepdims=False):
        out = T(self.d.sum(axis=axis, keepdims=keepdims), (self,))

        def back():
            g = out.grad
            if axis is not None and not keepdims:
                g = np.expand_dims(g, axis)
            self._accum(np.broadcast_to(g, self.d.shape).copy())
        out._back = back
        return out

    def mean(self, axis=None, keepdims=False):
        n = self.d.size if axis is None else self.d.shape[axis]
        return self.sum(axis=axis, keepdims=keepdims) * (1.0 / n)

    def tanh(self):
        y = np.tanh(self.d)
        out = T(y, (self,))

        def back():
            self._accum(out.grad * (1 - y * y))
        out._back = back
        return out

    def relu(self):
        out = T(np.maximum(self.d, 0), (self,))

        def back():
            self._accum(out.grad * (self.d > 0))
        out._back = back
        return out

    def sigmoid(self):
        y = 1.0 / (1.0 + np.exp(-self.d))
        out = T(y, (self,))

        def back():
            self._accum(out.grad * y * (1 - y))
        out._back = back
        return out

    def softmax_last(self):
        z = self.d - self.d.max(axis=-1, keepdims=True)
        e = np.exp(z)
        s = e / e.sum(axis=-1, keepdims=True)
        out = T(s, (self,))

        def back():
            g = out.grad
            dot = (g * s).sum(axis=-1, keepdims=True)
            self._accum(s * (g - dot))
        out._back = back
        return out


def _unbroadcast(g, shape):
    """브로드캐스트로 늘어난 축의 기울기를 원래 shape로 합산."""
    while g.ndim > len(shape):
        g = g.sum(axis=0)
    for i, (gs, ss) in enumerate(zip(g.shape, shape)):
        if ss == 1 and gs != 1:
            g = g.sum(axis=i, keepdims=True)
    return g.reshape(shape)


def embedding(W, idx):
    """W: T(V,d), idx: int 배열(...,) → T(...,d). 기울기는 행 산포 합산."""
    idx = np.asarray(idx)
    out = T(W.d[idx], (W,))

    def back():
        g = np.zeros_like(W.d)
        np.add.at(g, idx.reshape(-1), out.grad.reshape(-1, W.d.shape[1]))
        W._accum(g)
    out._back = back
    return out


def cross_entropy(logits, labels):
    """logits: T(B,C), labels: int(B,) → 평균 손실 스칼라."""
    labels = np.asarray(labels)
    z = logits.d - logits.d.max(axis=-1, keepdims=True)
    e = np.exp(z)
    p = e / e.sum(axis=-1, keepdims=True)
    B = labels.shape[0]
    loss = -np.log(np.clip(p[np.arange(B), labels], 1e-12, None)).mean()
    out = T(loss, (logits,))

    def back():
        g = p.copy()
        g[np.arange(B), labels] -= 1.0
        logits._accum(out.grad * g / B)
    out._back = back
    return out


class Adam:
    def __init__(self, params, lr=3e-3, b1=0.9, b2=0.999, eps=1e-8):
        self.params = params
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps
        self.m = [np.zeros_like(p.d) for p in params]
        self.v = [np.zeros_like(p.d) for p in params]
        self.t = 0

    def zero_grad(self):
        for p in self.params:
            p.grad = None

    def step(self):
        self.t += 1
        for i, p in enumerate(self.params):
            if p.grad is None:
                continue
            g = p.grad
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * g * g
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            p.d -= self.lr * mh / (np.sqrt(vh) + self.eps)


if __name__ == "__main__":
    # 수치 기울기 대조 검사 — 자동미분 자체의 정합성 증명
    rng = np.random.default_rng(0)
    W = T(rng.normal(size=(4, 3)) * 0.5)
    x = T(rng.normal(size=(2, 4)) * 0.5)
    labels = np.array([1, 2])

    def loss_val():
        h = x.matmul(W).tanh()
        return cross_entropy(h, labels)

    L = loss_val()
    L.backward()
    analytic = W.grad.copy()
    num = np.zeros_like(W.d)
    eps = 1e-6
    for i in range(W.d.shape[0]):
        for j in range(W.d.shape[1]):
            W.d[i, j] += eps
            lp = loss_val().d
            W.d[i, j] -= 2 * eps
            lm = loss_val().d
            W.d[i, j] += eps
            num[i, j] = (lp - lm) / (2 * eps)
    err = np.abs(analytic - num).max()
    print(f"gradcheck max_abs_err = {err:.2e}")
    assert err < 1e-6, "autograd FAILED gradient check"
    print("autograd OK")
