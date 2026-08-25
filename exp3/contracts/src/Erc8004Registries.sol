// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title ERC-8004 레지스트리 최소 구현 (Exp5 로컬 실험용)
/// @notice 스펙(eips.ethereum.org/EIPS/eip-8004, Draft/Review)의 함수 시그니처를 따르되
///         실험에 불필요한 부분은 단순화. 단순화 목록(정직성):
///         - IdentityRegistry: ERC-721 상속 생략(소유 매핑만), metadata 생략
///         - ValidationRegistry: getSummary의 validator 필터 인자 생략
///         스펙이 Review 단계라 인터페이스 변동 가능 — 어댑터로 취급할 것.
contract IdentityRegistry {
    uint256 public nextId = 1;
    mapping(uint256 => address) public agentWallet;
    mapping(uint256 => string) public agentURI;

    event Registered(uint256 indexed agentId, string agentURI, address indexed owner);

    function register(string calldata uri) external returns (uint256 agentId) {
        agentId = nextId++;
        agentWallet[agentId] = msg.sender;
        agentURI[agentId] = uri;
        emit Registered(agentId, uri, msg.sender);
    }

    function getAgentWallet(uint256 agentId) external view returns (address) {
        return agentWallet[agentId];
    }
}

contract ValidationRegistry {
    struct Val {
        address validator;
        uint256 agentId;
        uint8 response;      // 0~100
        bytes32 responseHash;
        string tag;
        uint64 lastUpdate;
        bool exists;
        bool responded;
    }

    mapping(bytes32 => Val) public vals;
    mapping(uint256 => bytes32[]) internal agentReqs;
    mapping(address => bytes32[]) internal validatorReqs;

    event ValidationRequest(address indexed validator, uint256 indexed agentId,
                            string requestURI, bytes32 requestHash);
    event ValidationResponse(address indexed validator, uint256 indexed agentId,
                             bytes32 requestHash, uint8 response, string tag);

    function validationRequest(address validatorAddress, uint256 agentId,
                               string calldata requestURI, bytes32 requestHash) external {
        require(!vals[requestHash].exists, "dup request");
        vals[requestHash] = Val(validatorAddress, agentId, 0, 0, "",
                                uint64(block.timestamp), true, false);
        agentReqs[agentId].push(requestHash);
        validatorReqs[validatorAddress].push(requestHash);
        emit ValidationRequest(validatorAddress, agentId, requestURI, requestHash);
    }

    function validationResponse(bytes32 requestHash, uint8 response,
                                string calldata, bytes32 responseHash,
                                string calldata tag) external {
        Val storage v = vals[requestHash];
        require(v.exists, "no request");
        require(msg.sender == v.validator, "not validator");
        require(response <= 100, "range");
        v.response = response;
        v.responseHash = responseHash;
        v.tag = tag;
        v.responded = true;
        v.lastUpdate = uint64(block.timestamp);
        emit ValidationResponse(msg.sender, v.agentId, requestHash, response, tag);
    }

    function getValidationStatus(bytes32 requestHash)
        external view
        returns (address validator, uint256 agentId, uint8 response, string memory tag, bool responded)
    {
        Val storage v = vals[requestHash];
        return (v.validator, v.agentId, v.response, v.tag, v.responded);
    }

    /// @notice 응답 완료된 검증들의 (건수, 평균 점수) — 온체인 평판의 원료
    function getSummary(uint256 agentId) external view returns (uint64 count, uint256 avgResponse) {
        bytes32[] storage reqs = agentReqs[agentId];
        uint256 sum;
        for (uint256 i = 0; i < reqs.length; i++) {
            Val storage v = vals[reqs[i]];
            if (v.responded) {
                count++;
                sum += v.response;
            }
        }
        avgResponse = count == 0 ? 0 : sum / count;
    }

    function getAgentValidations(uint256 agentId) external view returns (bytes32[] memory) {
        return agentReqs[agentId];
    }

    /// @notice 특정 태그를 제외한 (건수, 평균) — 기권 중립 평판의 원료 (Exp6).
    ///         스펙의 tag 필터 인자를 제외형으로 구현: "abstain"을 빼고 집계하면
    ///         기권이 평판을 깎지 않는다. 기권 건수는 getSummaryByTag로 별도 관측.
    function getSummaryExcluding(uint256 agentId, string calldata tag)
        external view returns (uint64 count, uint256 avgResponse)
    {
        bytes32 t = keccak256(bytes(tag));
        bytes32[] storage reqs = agentReqs[agentId];
        uint256 sum;
        for (uint256 i = 0; i < reqs.length; i++) {
            Val storage v = vals[reqs[i]];
            if (v.responded && keccak256(bytes(v.tag)) != t) {
                count++;
                sum += v.response;
            }
        }
        avgResponse = count == 0 ? 0 : sum / count;
    }

    /// @notice 특정 태그만의 건수 — 기권률 등 별도 신호 관측용.
    function getSummaryByTag(uint256 agentId, string calldata tag)
        external view returns (uint64 count)
    {
        bytes32 t = keccak256(bytes(tag));
        bytes32[] storage reqs = agentReqs[agentId];
        for (uint256 i = 0; i < reqs.length; i++) {
            Val storage v = vals[reqs[i]];
            if (v.responded && keccak256(bytes(v.tag)) == t) count++;
        }
    }
}
