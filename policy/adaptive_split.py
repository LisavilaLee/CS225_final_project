from dataclasses import dataclass


@dataclass
class NetworkScenario:
    """
    静态网络场景描述。

    所有字段都对应 emulation/main.py 的相关参数：
      - delay1_ms / delay2_ms -> --delay1 / --delay2 (毫秒)
      - loss1_pct / loss2_pct -> --loss1 / --loss2 (整数百分比)
      - bw1_mbps / bw2_mbps   -> --bw1 / --bw2 (Mbps)
      - cc                    -> tcp 子命令的 --congestion-control
    """
    scene_id: str
    delay1_ms: float
    delay2_ms: float
    loss1_pct: float
    loss2_pct: float
    bw1_mbps: float
    bw2_mbps: float
    cc: str  # 例如 "cubic"

    @property
    def rtt_ms(self) -> float:
        """近似 RTT（ms）：2 * (delay1 + delay2)."""
        return 2.0 * (self.delay1_ms + self.delay2_ms)

    @property
    def loss_pct(self) -> float:
        """近似端到端丢包率（百分比）：loss1 + loss2."""
        return self.loss1_pct + self.loss2_pct

    @property
    def bottleneck_bw_mbps(self) -> float:
        """近似瓶颈带宽：min(bw1, bw2)."""
        return min(self.bw1_mbps, self.bw2_mbps)


class AdaptiveSplitPolicy:
    """
    简单的 rule-based 自适应策略：

    - RTT 较高 且 丢包明显 -> 启用 splitting
    - 网络很好（RTT 短 且 几乎无丢包） -> 不启用 splitting
    - 其他情况按线性打分判断:
          score = alpha_rtt * RTT_ms + beta_loss * loss_pct
    """

    def __init__(
        self,
        rtt_high_ms: float = 50.0,
        loss_nontrivial_pct: float = 1.0,
        score_threshold: float = 80.0,
        alpha_rtt: float = 1.0,
        beta_loss: float = 5.0,
    ):
        self.rtt_high_ms = rtt_high_ms
        self.loss_nontrivial_pct = loss_nontrivial_pct
        self.score_threshold = score_threshold
        self.alpha_rtt = alpha_rtt
        self.beta_loss = beta_loss

    def score(self, scenario: NetworkScenario) -> float:
        """线性打分：score = alpha_rtt * RTT_ms + beta_loss * loss_pct."""
        return self.alpha_rtt * scenario.rtt_ms + self.beta_loss * scenario.loss_pct

    def should_split(self, scenario: NetworkScenario) -> bool:
        """
        返回是否启用 splitting（即是否加 --pep）。

        逻辑：
        - 高 RTT 且 loss 明显 -> True
        - 低 RTT 且 loss 极低 -> False
        - 其他 -> score >= 阈值 ?
        """
        s = self.score(scenario)

        # 高 RTT + 明显丢包：强制启用 splitting
        if scenario.rtt_ms >= self.rtt_high_ms and scenario.loss_pct >= self.loss_nontrivial_pct:
            return True

        # 网络很好：不启用 splitting
        if scenario.rtt_ms < self.rtt_high_ms / 2 and scenario.loss_pct < self.loss_nontrivial_pct / 2:
            return False

        # 其他情况：按得分判断
        return s >= self.score_threshold
