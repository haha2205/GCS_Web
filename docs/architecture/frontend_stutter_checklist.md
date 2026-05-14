# Apollo GCS Frontend 卡顿排查清单

## 目标

区分以下三类问题：

1. 后端 UDP 接收链路堵塞。
2. 后端已正常接收，但 WebSocket 推送或录制侧出现背压。
3. 后端正常，前端渲染层自身卡顿。

## 一、先看后端是否真的堵了

优先检查 `/health` 和 `/api/udp/status`。

重点指标：

- `pipeline.packet_processing_queue_size`
- `pipeline.recording_queue_size`
- `pipeline.online_analysis_queue_size`
- `pipeline.packet_drop_counters.processing_queue_coalesced`
- `pipeline.packet_drop_counters.processing_queue_full`
- `pipeline.packet_drop_counters.recording_queue_full`
- `pipeline.packet_drop_counters.online_analysis_queue_coalesced`
- `pipeline.packet_drop_counters.online_analysis_queue_full`

判读标准：

- 如果 queue size 长时间接近上限，说明后端消费速度跟不上输入速率。
- 如果 `processing_queue_coalesced` 持续上涨但系统仍响应，说明后端在按设计“丢旧保新”，不是全链路锁死。
- 如果 `recording_queue_full` 持续上涨，说明磁盘写入或录制线程是瓶颈。
- 如果 `online_analysis_queue_full` 持续上涨，说明在线分析 sidecar 或其网络链路偏慢。

## 二、判断是不是 WebSocket 推送侧的问题

现实现状：

- WebSocket 广播是并发发送，不是串行阻塞。
- 单连接发送有超时，超时连接会被清理。
- 高频遥测采用 latest-only 广播，不会无限排队。

如果仍怀疑 WebSocket：

- 看前端刷新后是否能立刻恢复到最新状态快照。
- 看 `websocket_connections` 数量是否异常波动。
- 看后端日志中是否出现大量连续广播异常。

判读标准：

- 如果前端断开重连后很快恢复，说明后端 WebSocket 管理基本正常。
- 如果 UDP 队列正常，但前端显示明显落后，问题更可能在前端消费或渲染。

## 三、判断是不是前端渲染层卡顿

典型现象：

- 后端 `/health` 指标正常。
- WebSocket 能持续收到最新数据。
- 但页面图表、姿态球、地图、表格存在掉帧或延迟感。

优先排查：

- ECharts 是否每帧全量 `setOption`。
- Three.js 场景是否反复重建对象。
- Vue 组件是否对高频遥测做了深层响应式追踪。
- 多个面板是否同时监听同一份高频数据并各自重复计算。
- 控制台是否有大量日志输出、watcher 抖动或重复 JSON 解析。

前端优化方向：

- 对高频遥测再做一次 UI 侧节流。
- 图表只更新增量点，不重建整条序列。
- 3D 场景只更新 transform，不频繁销毁重建 mesh。
- 将大对象拆成更细颗粒度状态，避免整个页面级联重渲染。

## 四、刷新前端是否会导致后端链路中断

当前后端设计下，不应该。

原因：

- UDP listener 生命周期独立于 WebSocket 生命周期。
- 前端刷新只会断开浏览器的 WebSocket。
- 后端会继续接收 UDP、继续解析、继续录制。
- 前端重连后会先收到后端缓存的最新状态快照。

如果刷新后看起来“像断了”，常见原因通常是：

- 前端重连后的页面初始化顺序有问题。
- 某个组件没有在重连后重新订阅状态。
- 页面恢复时被大体量图表渲染阻塞，看起来像后端没数据。

## 五、现场排查建议顺序

1. 刷新前端，同时观察后端 `/health` 指标是否连续变化。
2. 如果后端 queue 正常，先抓前端 Performance 面板看主线程占用。
3. 如果 recording queue 异常上涨，先关闭录制再对比流畅度。
4. 如果 online analysis queue 异常上涨，先断开 sidecar 再对比。
5. 如果只有某几个页面卡，优先检查对应图表或 3D 组件，而不是怀疑 UDP 主链路。