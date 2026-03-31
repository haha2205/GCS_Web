# DSM (Design Structure Matrix) 架构分析模块

本模块实现了基于HIL实测数据驱动的逻辑架构评价与优化核心逻辑。

## 目录结构
- **dsm_generator.py**: 
  - **功能**: 数据特征提取与DSM权重生成。
  - **输入**: HIL录制的原始CSV数据 (飞控/雷达/规划/总线)。
  - **核心算法**: 
    - 活跃度计算: `Weight = std(Cmd_Value)` (反映控制耦合强度)
    - 负载画像提取: `Profile = {CPU_Load, Data_Rate, Jitter}`
  - **输出**: JSON格式的加权DSM矩阵与功能画像。

- **evaluation_model.py**: 
  - **功能**: 架构评分与性能预测。
  - **输入**: DSM Report (JSON) + 架构分配方案 (Allocation Scheme)。
  - **核心模型**:
    1. **耦合代价 ($J_{coupling}$)**: 惩罚跨板高频交互。
    2. **延迟预测 ($J_{latency}$)**: 关键路径(Perception->Control)端到端延迟累加模型。
    3. **负载均衡 ($J_{balance}$)**: 板卡间CPU利用率方差。

- **verify_benchmark_dsm.py**: 
  - **用途**: 验证脚本。读取一段 HIL 录制数据，生成基准 DSM 报告 (JSON)。
  - **使用**: `python dsm/verify_benchmark_dsm.py`

- **run_architecture_scoring.py**: 
  - **用途**: 评价脚本。读取基准 DSM 报告，对比不同架构分配方案（如集中式 v.s. 分布式）的综合得分。
  - **使用**: `python dsm/run_architecture_scoring.py`

## 使用流程
1. **数据采集**: 使用 `recorder` 模块采集 HIL 测试场景数据。
2. **基准生成**: 运行 `verify_benchmark_dsm.py` 生成标准化的 DSM 数据集。
3. **架构寻优/评价**: 运行 `run_architecture_scoring.py` 对比不同部署方案的优劣。
