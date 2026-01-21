# DSM数据处理完整使用指南

## 📋 目录
1. [架构概述](#架构概述)
2. [双流数据流程](#双流数据流程)
3. [在线录制阶段](#在线录制阶段)
4. [映射配置阶段](#映射配置阶段)
5. [离线处理阶段](#离线处理阶段)
6. [使用示例](#使用示例)
7. [故障排查](#故障排查)

---

## 架构概述

### 核心理念
DSM算法采用**"事后分析"(Post-processing)** 模式，后端角色从"流处理器"转变为**"数据仓库 + 转换器"**。

### 双流处理架构

```
UDP数据接收
    ↓
    ├─→ [热流 Hot Stream] ← 实时计算推送到前端（监控用）
    │
    │   RealTimeCalculator
    │   ├─ 维度1: 算力资源监控
    │   ├─ 维度2: 通信指标计算
    │   ├─ 维度3: 能耗积分
    │   ├─ 维度4: 任务效能评估
    │   └─ 维度5: 飞行性能分析
    │
    │   → WebSocket推送给前端5维KPI监控面板
    │
    └─→ [冷流 Cold Stream] ← 全量录制到CSV文件（DSM分析用）
        │
        RawDataRecorder
        ├─ flight_perf.csv      # 飞行性能数据
        ├─ resources.csv        # 资源数据（CPU、内存）
        ├─ bus_traffic.csv      # 总线通信数据
        ├─ obstacles.csv        # 障碍物数据
        ├─ lidar_performance.csv # LiDAR性能数据
        ├─ lidar_status.csv     # LiDAR状态数据
        ├─ futaba_remote.csv    # Futaba遥控数据 ⭐ NEW
        └─ gncbus.csv          # GN&C总线数据 ⭐ NEW
              
              ↓
        DSMGenerator（离线处理）
        ├─ 读取CSV文件
        ├─ 时间切片过滤
        ├─ 根据MappingConfig聚合计算
        └─ 生成DSM格式文件
              ↓
        {dsm_report.json, dsm_matrix.csv}
              ↓
        DSM优化算法输入
```

---

## 双流数据流程

### 1. 热流（Hot Stream）- 实时监控
**目标**: 低延迟、实时推送KPI指标给前端监控面板

**处理流程**:
```
UDP数据包 → 协议解析 → RealTimeCalculator → WebSocket推送 → 前端5维监控面板
```

**输出内容**:
- 算力资源: CPU负载、内存使用率、评分
- 通信资源: 抖动(ms)、丢包率(%)、评分
- 能耗指标: 功率(W)、累计能耗(kWh)、评分
- 任务效能: 进度(%)、安全余量(%)、评分
- 飞行性能: RMSE(m)、姿态稳定性、评分

**刷新频率**: 20Hz以内（避免过度刷新UI）

### 2. 冷流（Cold Stream）- DSM离线分析
**目标**: 高质量、全量记录原始数据用于DSM算法分析

**处理流程**:
```
UDP数据包 → 协议解析 → RawDataRecorder → CSV文件存储
                                                         ↓
                                                 用户点击"生成DSM报告"
                                                         ↓
                                   DSMGenerator读取CSV + MappingConfig聚合
                                                         ↓
                                              生成DSM标准格式文件
```

**支持的数据类型**:
| 数据类型 | 文件名 | 关键字段 | 用途 |
|---------|--------|---------|------|
| 飞行性能 | flight_perf.csv | lat, lon, alt, roll, pitch, yaw | 计算飞行性能指标 |
| 资源数据 | resources.csv | node_id, cpu_load, exec_time | 计算节点权重 |
| 总线通信 | bus_traffic.csv | msg_id, msg_size, frequency | 计算交互权重 |
| Futaba遥控 | futaba_remote.csv ⭐ | remote_roll, pitch, yaw, throttle | 计算遥控输入权重 |
| GN&C总线 | gncbus.csv ⭐ | cmd_phi, cmd_vx, cmd_height | 计算GNC指令权重 |
| 障碍物数据 | obstacles.csv | position_x/y/z, distance | 避障效能评估 |
| LiDAR性能 | lidar_performance.csv | processing_time_ms, frame_rate | 传感器性能分析 |

---

## 在线录制阶段

### 启动录制

**前端操作**:
1. 打开左侧"配置"面板
2. 点击"开始录制"按钮
3. 系统自动生成session_id（格式: `20260119_143052`）

**后端处理**:
```python
# 1. 创建会话目录
data/20260119_143052/

# 2. 初始化8个CSV文件，并写入表头
- flight_perf.csv      # 表头: timestamp, lat, lon, alt, ...
- resources.csv        # 表头: timestamp, node_id, cpu_load, ...
- bus_traffic.csv      # 表头: timestamp, msg_id, msg_size, ...
- futaba_remote.csv    # 表头: timestamp, remote_roll, ... ⭐ NEW
- gncbus.csv          # 表头: timestamp, cmd_phi, ...     ⭐ NEW
- obstacles.csv
- lidar_performance.csv
- lidar_status.csv

# 3. 打开文件句柄保持连接，避免频繁IO
# 4. 实时追加写入数据行
```

### 数据写入逻辑

**实时数据处理**:
```python
def record_decoded_packet(self, decoded_data: dict):
    """统一的UDP数据包记录入口"""
    msg_type = decoded_data.get('type', 'unknown')
    data = decoded_data.get('data', {})
    
    # 根据消息类型分发到对应的CSV文件
    if msg_type == 'fcs_states':
        self.record_flight_perf(data)
    elif msg_type == 'fcs_datafutaba':  # ⭐ NEW: Futaba遥控数据
        self.record_futaba(data)
        # 写入格式: timestamp, remote_roll, remote_pitch, remote_yaw, remote_throttle, remote_switch, remote_fail
    elif msg_type == 'fcs_gncbus':  # ⭐ NEW: GNC总线数据
        self.record_gncbus(data)
        # 写入格式: timestamp, cmd_phi, cmd_hdot, cmd_r, cmd_psi, cmd_vx, cmd_vy, cmd_height
    elif msg_type in ['fcs_param', 'fcs_datactrl']:
        self.record_resources(data)
    # ... 其他类型
```

### 停止录制

**前端操作**: 点击"停止录制"按钮

**后端处理**:
```python
# 1. 关闭所有文件句柄
for file_handle in self.file_handles.values():
    file_handle.close()

# 2. 统计数据
data_counters = {
    'flight_perf': 15234,        # 飞行性能记录数
    'resources': 15234,            # 资源记录数
    'bus_traffic': 15234,          # 总线记录数
    'futaba_remote': 15234,        # 遥控记录数 ⭐ NEW
    'gncbus': 15234,              # GNC总线记录数 ⭐ NEW
    'obstacles': 450,              # 障碍物记录数
    'lidar_performance': 15234,    # LiDAR性能记录数
    'lidar_status': 300            # LiDAR状态记录数
}

# 3. 广播会话结束消息
await manager.broadcast({
    "type": "recording_status",
    "is_active": False,
    "session_id": "20260119_143052",
    "session_info": {...}
})
```

---

## 映射配置阶段

### 配置文件结构

配置文件采用YAML格式，定义**物理数据 → 逻辑架构**的映射关系：

**文件位置**: `Apollo-GCS-Web/src-python/config/mapping_config.yaml`

### 节点映射（Nodes）

用于计算**DSM对角线权重**（节点自身代价）

```yaml
nodes:
  # 示例1: 导航逻辑功能
  - logical_function: 'LF_Navigation'
    physical_source:
      type: 'cpu_load'              # 数据源类型
      filter_id: 0x42                # fcs_states消息ID
      metric: 'avg_load'            # 使用平均负载
      description: '导航任务'

  # 示例2: 电机控制逻辑功能
  - logical_function: 'LF_Motor_Control'
    physical_source:
      type: 'cpu_load'
      filter_id: 0x41                # fcs_pwms消息ID
      metric: 'peak_load'           # 使用峰值负载
      description: '电机控制'

  # 示例3: 飞控核心功能
  - logical_function: 'LF_Flight_Controller'
    physical_source:
      type: 'cpu_load'
      filter_id: 0x43                # fcs_datactrl消息ID
      metric: 'avg_load'
      description: '飞控核心功能'

  # 示例4: 避障功能
  - logical_function: 'LF_Obstacle_Avoidance'
    physical_source:
      type: 'cpu_load'
      filter_id: 0x45                # avoiflag消息ID
      metric: 'peak_load'
      description: '避障功能'

  # 示例5: 传感器融合
  - logical_function: 'LF_Sensor_Fusion'
    physical_source:
      type: 'cpu_load'
      filter_id: 0x44                # fcs_gncbus消息ID
      metric: 'avg_load'
      description: '传感器融合'

  # 示例6: ESC管理
  - logical_function: 'LF_ESC_Management'
    physical_source:
      type: 'cpu_load'
      filter_id: 0x4B                # fcs_esc消息ID
      metric: 'avg_load'
      description: 'ESC管理'

  # ⭐ 示例7: 飞行员输入（NEW）
  - logical_function: 'LF_Pilot_Input'
    physical_source:
      type: 'control_input'        # ⭐ 新数据源：遥控器输入
      filter_id: 0x46                # fcs_datafutaba消息ID
      metric: 'avg_throttle'
      description: '飞行员输入 - 遥控器输入处理'

  # ⭐ 示例8: GN&C制导（NEW）
  - logical_function: 'LF_GNC_Guidance'
    physical_source:
      type: 'gnc_command'          # ⭐ 新数据源：GNC指令
      filter_id: 0x44                # fcs_gncbus消息ID
      metric: 'cmd_vx_avg'
      description: 'GN&C制导 - 导航制导指令生成'
```

**支持的数据源类型**:
1. `cpu_load`: CPU负载数据（resources.csv）
2. `control_input`: 遥控器输入数据（futaba_remote.csv）⭐ NEW
3. `gnc_command`: GNC指令数据（gncbus.csv）⭐ NEW

**支持的指标类型**:
- `avg_load`: 平均负载
- `peak_load`: 峰值负载
- `avg_throttle`: 平均油门
- `avg_roll`, `avg_pitch`, `avg_yaw`: 平均姿态输入
- `cmd_phi_std`: 指令变化标准差
- `cmd_vx_avg`: 平均速度指令

### 交互映射（Edges）

用于计算**DSM非对角线权重**（模块间依赖强度）

```yaml
edges:
  # 遥控输入相关
  - functional_exchange: 'FE_Remote_Control_Input'
    source_lf: 'LF_Pilot_Input'       # 飞行员输入
    target_lf: 'LF_Flight_Controller' # → 飞控
    physical_source:
      type: 'remote_input_activity' ⭐ NEW
      filter_id: 0x46
      weight_formula: 'activity'        # 权重 = 遥控输入活动度
      description: '遥控器输入发送到飞控'

  # 导航数据流
  - functional_exchange: 'FE_Nav_State_Transmission'
    source_lf: 'LF_Navigation'
    target_lf: 'LF_Flight_Controller'
    physical_source:
      type: 'bus_traffic'
      filter_id: 0x42               # fcs_states消息ID
      weight_formula: 'frequency * size'  # 权重 = 频率 × 大小
      description: '导航状态传输到飞控'

  # 电机控制流
  - functional_exchange: 'FE_Motor_Command'
    source_lf: 'LF_Flight_Controller'
    target_lf: 'LF_Motor_Control'
    physical_source:
      type: 'bus_traffic'
      filter_id: 0x41               # fcs_pwms消息ID
      weight_formula: 'frequency * size'
      description: '飞控发送电机命令'

  # GNC指令流（NEW）
  - functional_exchange: 'FE_GNC_Command_Generation'
    source_lf: 'LF_GNC_Guidance'    # GN&C制导
    target_lf: 'LF_Flight_Controller'
    physical_source:
      type: 'gnc_command_change' ⭐ NEW
      filter_id: 0x44
      weight_formula: 'std'             # 权重 = 指令变化标准差
      description: 'GNC制导指令传输到飞控'

  # ... 其他交互映射
```

**支持的数据源类型**:
1. `bus_traffic`: 总线通信数据（bus_traffic.csv）
2. `gnc_command_change`: GNC指令变化数据（gncbus.csv）⭐ NEW
3. `remote_input_activity`: 遥控输入活动数据（futaba_remote.csv）⭐ NEW

**权重公式变量**:
- `count`: 消息数量
- `frequency`: 消息频率（msg/s）
- `size`: 消息大小（字节）
- `latency`: 延迟（ms）
- `std`: 标准差（用于指令变化）
- `activity`: 活动度（用于遥控输入）

### 动态更新配置

```python
# 通过API更新配置
POST /api/dsm/config
{
  "nodes": [...],
  "edges": [...]
}

# 配置更新后，DSM生成器自动重新加载
dsm_generator = DSMGenerator(mapping_config)
```

---

## 离线处理阶段

### DSM报告生成流程

**用户操作**:
1. 打开右侧"监控"面板的"系统性能"标签页
2. 点击"导出DSM数据"按钮
3. 选择录制会话、配置参数
4. 点击"生成DSM报告"

**后端处理**:

```python
# 1. 加载原始CSV数据
df_flight = pd.read_csv('data/20260119_143052/flight_perf.csv')
df_resources = pd.read_csv('data/20260119_143052/resources.csv')
df_bus = pd.read_csv('data/20260119_143052/bus_traffic.csv')
df_futaba = pd.read_csv('data/20260119_143052/futaba_remote.csv')  # ⭐ NEW
df_gncbus = pd.read_csv('data/20260119_143052/gncbus.csv')          # ⭐ NEW
# ... 其他数据文件

# 2. 时间切片过滤（如果指定）
df_flight = df_flight[(df_flight['timestamp'] >= start_time) & 
                            (df_flight['timestamp'] <= end_time)]
# ... 对所有数据框应用同样过滤

# 3. 计算节点权重（对角线）
for node_cfg in mapping_config.get_nodes():
    lf_name = node_cfg['logical_function']
    data_type = node_cfg['physical_source']['type']
    
    if data_type == 'cpu_load':
        # 使用resources.csv中的CPU数据
        node_data = df_resources[df_resources['task_id'] == node_id]
        weight = node_data['cpu_load'].mean()
    
    elif data_type == 'control_input':  # ⭐ NEW
        # 使用futaba_remote.csv中的遥控输入数据
        if node_cfg['metric'] == 'avg_throttle':
            weight = df_futaba['remote_throttle'].mean() / 2000.0
    
    elif data_type == 'gnc_command':  # ⭐ NEW
        # 使用gncbus.csv中的GNC指令数据
        if node_cfg['metric'] == 'cmd_vx_avg':
            weight = df_gncbus['cmd_vx'].mean() / 10.0
    
    dsm_nodes.append({
        "index": i,
        "name": lf_name,
        "own_cost": round(weight, 4),  # 对角线值
        "attributes": {...}
    })

# 4. 计算交互权重（非对角线）
for edge_cfg in mapping_config.get_edges():
    source_lf = edge_cfg['source_lf']
    target_lf = edge_cfg['target_lf']
    data_type = edge_cfg['physical_source']['type']
    
    if data_type == 'bus_traffic':
        # 使用bus_traffic.csv
        msg_data = df_bus[df_bus['msg_id'] == msg_id]
        count = len(msg_data)
        frequency = count / duration
        avg_size = msg_data['msg_size'].mean()
        weight = frequency * avg_size  # 应用公式
    
    elif data_type == 'gnc_command_change':  # ⭐ NEW
        # 使用gncbus.csv计算指令变化率
        cmd_values = df_gncbus[cmd_column].values
        std_val = np.std(cmd_values)  # 标准差反映变化频率
        weight = std_val
    
    elif data_type == 'remote_input_activity':  # ⭐ NEW
        # 使用futaba_remote.csv计算遥控活动度
        input_values = df_futaba[input_column].values
        diff_values = np.abs(np.diff(input_values))  # 一阶差分
        activity_score = np.mean(diff_values)
        weight = activity_score
    
    if weight > 0:
        dsm_edges.append({
            "from": source_lf,
            "to": target_lf,
            "weight": round(weight, 4),  # 非对角线值
            "type": "DataFlow",
            "functional_exchange": edge_cfg['functional_exchange'],
            "attributes": {...}
        })

# 5. 构建DSM矩阵
n = len(dsm_nodes)
matrix = np.zeros((n, n))

# 填充对角线
for i, node in enumerate(dsm_nodes):
    matrix[i, i] = node['own_cost']

# 填充非对角线
node_name_to_index = {node['name']: node['index'] for node in dsm_nodes}
for edge in dsm_edges:
    i = node_name_to_index[edge['from']]
    j = node_name_to_index[edge['to']]
    matrix[i, j] = edge['weight']

# 6. 生成输出文件
# 格式1: JSON（推荐，易于扩展）
dsm_report = {
  "meta": {
    "session_id": "20260119_143052",
    "scenario": "Obstacle_Avoidance",
    "duration": 60.5,
    "data_statistics": {
      "flight_records": 15234,
      "resource_records": 15234,
      "bus_records": 15234,
      "futaba_records": 15234,  # ⭐ NEW
      "gncbus_records": 15234      # ⭐ NEW
    }
  },
  "nodes": dsm_nodes,
  "edges": dsm_edges,
  "matrix": matrix.tolist()
}

# 保存为JSON
with open('data/20260119_143052/dsm_report.json', 'w') as f:
    json.dump(dsm_report, f, indent=2)

# 格式2: CSV矩阵（适合MATLAB/NumPy直接读取）
with open('data/20260119_143052/dsm_matrix.csv', 'w') as f:
    writer = csv.writer(f)
    # 写入表头
    header = [''] + [node['name'] for node in dsm_nodes]
    writer.writerow(header)
    # 写入矩阵数据
    for i, row in enumerate(matrix):
        row_data = [dsm_nodes[i]['name']] + [f"{val:.4f}" for val in row]
        writer.writerow(row_data)
```

### 输出格式

#### 格式1: JSON标准格式（推荐）

```json
{
  "meta": {
    "session_id": "20260119_143052",
    "generated_at": "2026-01-19T14:30:52.123456",
    "time_range": {
      "start": 1737269252.0,
      "end": 1737269812.5,
      "duration": 60.5
    },
    "data_statistics": {
      "flight_records": 15234,
      "resource_records": 15234,
      "bus_records": 15234,
      "futaba_records": 15234,
      "gncbus_records": 15234
    }
  },
  "matrix_elements": [
    {"index": 0, "name": "LF_Navigation", "own_cost": 45.2},
    {"index": 1, "name": "LF_Motor_Control", "own_cost": 20.1},
    {"index": 2, "name": "LF_Flight_Controller", "own_cost": 80.5},
    {"index": 3, "name": "LF_Obstacle_Avoidance", "own_cost": 15.8},
    {"index": 4, "name": "LF_Sensor_Fusion", "own_cost": 60.3},
    {"index": 5, "name": "LF_ESC_Management", "own_cost": 10.2},
    {"index": 6, "name": "LF_Pilot_Input", "own_cost": 35.7},
    {"index": 7, "name": "LF_GNC_Guidance", "own_cost": 50.6}
  ],
  "dependencies": [
    {"source": 0, "target": 1, "strength": 1200.0},
    {"source": 1, "target": 2, "strength": 850.0},
    {"source": 2, "target": 0, "strength": 5000.0},
    {"source": 4, "target": 3, "strength": 2300.0},
    {"source": 6, "target": 2, "strength": 1500.0},
    {"source": 7, "target": 2, "strength": 3200.0}
  ],
  "matrix": [
    [45.2000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
    [0.0000, 20.1000, 850.0000, 0.0000, 0.0000, 1200.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 80.5000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 0.0000, 15.8000, 0.0000, 0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 0.0000, 2300.0000, 60.3000, 0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 10.2000, 0.0000, 0.0000],
    [0.0000, 0.0000, 1500.0000, 0.0000, 0.0000, 0.0000, 35.7000, 0.0000],
    [0.0000, 0.0000, 3200.0000, 0.0000, 0.0000, 0.0000, 0.0000, 50.6000]
  ]
}
```

#### 格式2: CSV矩阵格式（适合MATLAB）

```csv
,LF_Navigation,LF_Motor_Control,LF_Flight_Controller,LF_Obstacle_Avoidance,LF_Sensor_Fusion,LF_ESC_Management,LF_Pilot_Input,LF_GNC_Guidance
LF_Navigation,45.2000,0.0000,0.0000,0.0000,0.0000,0.0000,0.0000,0.0000
LF_Motor_Control,0.0000,20.1000,850.0000,0.0000,0.0000,1200.0000,0.0000,0.0000
LF_Flight_Controller,0.0000,0.0000,80.5000,0.0000,0.0000,0.0000,0.0000,0.0000
LF_Obstacle_Avoidance,0.0000,0.0000,0.0000,15.8000,0.0000,0.0000,0.0000,0.0000
LF_Sensor_Fusion,0.0000,0.0000,0.0000,2300.0000,60.3000,0.0000,0.0000,0.0000
LF_ESC_Management,0.0000,0.0000,0.0000,0.0000,0.0000,10.2000,0.0000,0.0000
LF_Pilot_Input,0.0000,0.0000,1500.0000,0.0000,0.0000,0.0000,35.7000,0.0000
LF_GNC_Guidance,0.0000,0.0000,3200.0000,0.0000,0.0000,0.0000,0.0000,50.6000
```

---

## 使用示例

### 完整工作流程

#### 场景1: 一次完整的飞控数据录制和DSM分析

```
【步骤1: 启动系统】
1. 启动后端服务
   cd Apollo-GCS-Web/src-python
   python main.py

2. 启动前端开发服务器
   cd Apollo-GCS-Web/src-frontend
   npm run dev

3. 配置UDP连接（IP: 192.168.1.100, Port: 18504）

【步骤2: 开始录制】
1. 在前端左侧"配置"面板，点击"开始录制"
2. 系统生成session_id: "20260119_143052"
3. 后端创建目录: data/20260119_143052/
4. 后端打开8个CSV文件并写入表头

【步骤3: 执行飞行任务】
1. 无人机执行"自主避障"任务
2. 持续时间: 60秒
3. 实时监控5维KPI指标（热流推送）
   - 算力资源: CPU 65%, 评分: 0.78
   - 通信资源: 抖动 2.5ms, 丢包率 0.1%, 评分: 0.95
   - 能耗指标: 功率 320W, 累计 19.2kJ, 评分: 0.85
   - 任务效能: 进度 80%, 安全余量 35%, 评分: 0.82
   - 飞行性能: RMSE 0.8m, 评分: 0.90

【步骤4: 停止录制】
1. 飞行任务完成后，点击"停止录制"
2. 后端统计数据总数:
   - flight_perf: 15234 条
   - resources: 15234 条
   - bus_traffic: 15234 条
   - futaba_remote: 15234 条  (⭐ NEW)
   - gncbus: 15234 条         (⭐ NEW)
   - obstacles: 450 条
   - lidar_performance: 15234 条
   - lidar_status: 300 条

【步骤5: 生成DSM报告】
1. 在前端右侧"监控"面板，切换到"系统性能"标签页
2. 点击"导出DSM数据"按钮
3. 选择会话: "20260119_143052"
4. 配置参数:
   - 时间范围: 全时段
   - 映射配置: 默认配置
   - 输出格式: JSON + CSV矩阵
5. 点击"生成DSM报告"

【步骤6: 查看结果】
1. 等待生成完成（通常< 5秒）
2. 查看生成结果:
   - 节点数量: 8
   - 交互数量: 6
   - 分析时长: 2.3秒
3. 下载生成的文件:
   - DSM数据结构.json (8KB)
   - DSM矩阵.csv (1.2KB)

【步骤7: 优化架构】
1. 读取JSON文件到DSM优化算法
2. 运行聚类算法（如：层次聚类、K-means）
3. 生成优化后的架构方案
4. 评估优化效果（成本降低%）
```

#### 场景2: 时间切片分析（只分析关键时刻）

```
【需求】
只分析"自主避障"关键时刻（第30-45秒）的DSM数据

【操作】
1. 在DSM导出界面，选择"自定义范围"时间范围
2. 设置:
   - 开始时间: 2026-01-19T14:30:30
   - 结束时间: 2026-01-19T14:30:45
3. 点击"生成DSM报告"

【后端处理】
# 时间切片过滤
df_flight = df_flight[(df_flight['timestamp'] >= 1737266630.0) & 
                            (df_flight['timestamp'] <= 1737267545.0)]
# 时间范围: 15秒 = 750个数据点（50Hz）

# 计算该时间段的节点权重
node_1_weight = df_resources['cpu_load'].mean()  # 该段平均CPU负载
# 只使用切片时间段的数据

生成DSM报告，包含15秒的数据统计
```

#### 场景3: 动态调整映射配置

```
【需求】
逻辑架构优化后，需要调整映射关系

【操作】
1. 编辑 mapping_config.yaml
   - 添加新节点: 'LF_Path_Planning'
   - 修改交互: 添加新的数据流
2. 通过API更新配置:
   POST /api/dsm/config
   {
     "nodes": [...],
     "edges": [...]
   }

【自动处理】
1. 后端验证配置格式
2. 重新创建DSM生成器
3. 广播配置更新消息
4. 下次生成DSM报告时使用新配置
```

---

## 故障排查

### 常见问题1: 协议解析失败

**现象**:
```
[协议解析] ⚠ ExtY_FCS_DATAFUTABA_T解析失败: Payload长度不足: 8 < 10
```

**原因**: 
Futaba遥控数据包（0x46）的payload长度不正确

**解决**:
```python
# 检查实际接收的payload长度
print(f"Received payload length: {len(payload)}, required: 10")

# 如果长度不一致，检查飞控发送格式
# ExtY_FCS_DATAFUTABA_T应该是10字节:
# - Tele_ftb_Roll: uint16 (2字节)
# - Tele_ftb_Pitch: uint16 (2字节)
# - Tele_ftb_Yaw: uint16 (2字节)
# - Tele_ftb_Col: uint16 (2字节)
# - Tele_ftb_Switch: int8 (1字节)
# - Tele_ftb_com_Ftb_fail: int8 (1字节)
# 总计: 10字节
```

### 常见问题2: DSM生成报告时找不到数据

**现象**:
```
[DSM生成] ⚠ 加载Futaba遥控数据: 0 条记录
[DSM生成] ⚠ 加载GN&C总线数据: 0 条记录
```

**原因**: 
录制时没有接收到0x46（Futaba）和0x44（GNCBUS）消息

**解决**:
1. 检查飞控是否发送这些消息类型
2. 检查协议解析器是否正确处理0x46功能码
3. 检查录制器是否正确路由这些消息类型

```python
# 在 on_udp_message_received 中添加调试日志
msg_type = message.get('type', 'unknown')
func_code = message.get('func_code', 0)

if msg_type == 'fcs_datafutaba':
    logger.info(f"接收到Futaba遥控数据: {message['data']}")
elif msg_type == 'fcs_gncbus':
    logger.info(f"接收到GN&C总线数据: {message['data']}")
```

### 常见问题3: CSV文件中文乱码

**现象**:
打开CSV文件时中文显示乱码

**原因**:
文件编码问题

**解决**:
```python
# 使用UTF-8编码打开CSV文件
with open(flight_path, 'r', encoding='utf-8') as f:
    df = pd.read_csv(f)

# 写入时也使用UTF-8
with open(output_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
```

### 常见问题4: DSM矩阵全为0

**现象**:
生成的DSM矩阵所有值都是0

**原因**:
1. 映射配置中的filter_id与实际接收的msg_id不匹配
2. 数据过滤条件过于严格

**解决**:
```python
# 在DSM生成器中添加详细日志
for node_cfg in mapping_config.get_nodes():
    filter_id = node_cfg['physical_source']['filter_id']
    type = node_cfg['physical_source']['type']
    
    # 打印过滤条件
    logger.info(f"节点: {node_cfg['logical_function']}, "
                f"type: {type}, filter_id: 0x{filter_id:02X}")
    
    if type == 'bus_traffic':
        filtered_df = df_bus[df_bus['msg_id'] == filter_id]
        logger.info(f"  过滤后数据量: {len(filtered_df)} / {len(df_bus)}")
```

---

## 性能优化建议

### 1. 数据录制优化

```python
# 定期刷新缓冲区，避免频繁IO
if self.data_counters[filename] % 100 == 0:
    self.file_handles[filename].flush()

# 使用缓冲写入
import io
buffer = io.StringIO()
writer = csv.writer(buffer)
writer.writerow([...])

# 批量写入
if len(buffer.getvalue()) > 4096:  # 4KB批量写入
    file_handle.write(buffer.getvalue())
    buffer.truncate(0)
```

### 2. DSM生成优化

```python
# 使用pandas向量化操作代替循环
# 慢速方式（不推荐）
weight = 0
for i in range(len(df)):
    weight += df['cpu_load'].iloc[i]
weight /= len(df)

# 快速方式（推荐）
weight = df['cpu_load'].mean()

# 使用numpy高效计算
import numpy as np
std_val = np.std(df_gncbus['cmd_vx'].values)
```

### 3. 内存管理优化

```python
# 大数据集分块处理
chunk_size = 10000
for chunk in pd.read_csv('large_file.csv', chunksize=chunk_size):
    process_chunk(chunk)
    
# 及时释放内存
del df
import gc
gc.collect()
```

---

## 总结

本DSM数据处理方案的核心优势：

1. **解耦**: 实时监控和DSM数据生成互不干扰
2. **灵活**: 逻辑架构变化只需修改mapping_config.yaml
3. **可追溯**: 所有原始数据保存为CSV，支持复现
4. **可扩展**: 支持多种数据源（CPU、遥控、GNC指令）
5. **多格式**: 支持JSON和CSV矩阵两种输出格式

通过这套完整的数据处理流程，您可以：
- 实时监控无人机5维KPI指标
- 离线生成DSM算法所需的标准化输入文件
- 分析不同时间段的架构性能
- 为架构优化提供数据支撑