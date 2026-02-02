<template>
  <div class="params-panel">
    <h3 class="panel-title">参数配置</h3>
    
    <div class="content-scroll" :class="{ 'btn-disabled': !connected }">
      <div class="params-content">
        <div class="params-sections">
      <!-- PID参数组 -->
      <div class="params-group">
        <div class="section-header">
          <h4 class="section-title" @click="toggleSection('pid')">
            <span class="section-icon" :class="{ expanded: expandedSections.pid }">▼</span>
            PID参数调试
          </h4>
          <button class="icon-btn refresh" @click="readPids" title="读取参数">↻</button>
        </div>
        
        <div v-show="expandedSections.pid" class="params-content">
          <div class="pid-groups">
            <!-- 滚转控制 -->
            <div class="pid-group">
              <h5 class="pid-group-title">滚转控制 (Roll Control)</h5>
              <div class="pid-row">
                <label>F_KaPHI (滚转角P)</label>
                <input v-model.number="pid.fKaPHI" type="number" class="pid-input" step="0.001" placeholder="0.5" />
              </div>
              <div class="pid-row">
                <label>F_KaP (滚转角D)</label>
                <input v-model.number="pid.fKaP" type="number" class="pid-input" step="0.001" placeholder="0.2" />
              </div>
              <div class="pid-row">
                <label>F_KaY (横向位置P)</label>
                <input v-model.number="pid.fKaY" type="number" class="pid-input" step="0.001" placeholder="0.143" />
              </div>
              <div class="pid-row">
                <label>F_IaY (横向位置I)</label>
                <input v-model.number="pid.fIaY" type="number" class="pid-input" step="0.001" placeholder="0.005" />
              </div>
              <div class="pid-row">
                <label>F_KaVy (横向速度P)</label>
                <input v-model.number="pid.fKaVy" type="number" class="pid-input" step="0.001" placeholder="2.0" />
              </div>
              <div class="pid-row">
                <label>F_IaVy (横向速度I)</label>
                <input v-model.number="pid.fIaVy" type="number" class="pid-input" step="0.001" placeholder="0.4" />
              </div>
              <div class="pid-row">
                <label>F_KaAy (横向加速度D)</label>
                <input v-model.number="pid.fKaAy" type="number" class="pid-input" step="0.001" placeholder="0.28" />
              </div>
            </div>
            
            <!-- 俯仰控制 -->
            <div class="pid-group">
              <h5 class="pid-group-title">俯仰控制 (Pitch Control)</h5>
              <div class="pid-row">
                <label>F_KeTHETA (俯仰角P)</label>
                <input v-model.number="pid.fKeTHETA" type="number" class="pid-input" step="0.001" placeholder="0.5" />
              </div>
              <div class="pid-row">
                <label>F_KeQ (俯仰角D)</label>
                <input v-model.number="pid.fKeQ" type="number" class="pid-input" step="0.001" placeholder="0.2" />
              </div>
              <div class="pid-row">
                <label>F_KeX (纵向位置P)</label>
                <input v-model.number="pid.fKeX" type="number" class="pid-input" step="0.001" placeholder="0.201" />
              </div>
              <div class="pid-row">
                <label>F_IeX (纵向位置I)</label>
                <input v-model.number="pid.fIeX" type="number" class="pid-input" step="0.001" placeholder="0.01" />
              </div>
              <div class="pid-row">
                <label>F_KeVx (纵向速度P)</label>
                <input v-model.number="pid.fKeVx" type="number" class="pid-input" step="0.001" placeholder="2.0" />
              </div>
              <div class="pid-row">
                <label>F_IeVx (纵向速度I)</label>
                <input v-model.number="pid.fIeVx" type="number" class="pid-input" step="0.001" placeholder="0.4" />
              </div>
              <div class="pid-row">
                <label>F_KeAx (纵向加速度D)</label>
                <input v-model.number="pid.fKeAx" type="number" class="pid-input" step="0.001" placeholder="0.55" />
              </div>
            </div>

            <!-- 偏航控制 -->
            <div class="pid-group">
              <h5 class="pid-group-title">偏航控制 (Yaw Control)</h5>
              <div class="pid-row">
                <label>F_KrR (偏航角速度P)</label>
                <input v-model.number="pid.fKrR" type="number" class="pid-input" step="0.001" placeholder="0.2" />
              </div>
              <div class="pid-row">
                <label>F_IrR (偏航角速度I)</label>
                <input v-model.number="pid.fIrR" type="number" class="pid-input" step="0.001" placeholder="0.01" />
              </div>
              <div class="pid-row">
                <label>F_KrAy (偏航加速度P)</label>
                <input v-model.number="pid.fKrAy" type="number" class="pid-input" step="0.001" placeholder="0.1" />
              </div>
              <div class="pid-row">
                <label>F_KrPSI (偏航角P)</label>
                <input v-model.number="pid.fKrPSI" type="number" class="pid-input" step="0.001" placeholder="1.0" />
              </div>
            </div>

            <!-- 高度控制 -->
            <div class="pid-group">
              <h5 class="pid-group-title">高度控制 (Altitude Control)</h5>
              <div class="pid-row">
                <label>F_KcH (高度P)</label>
                <input v-model.number="pid.fKcH" type="number" class="pid-input" step="0.001" placeholder="0.36" />
              </div>
              <div class="pid-row">
                <label>F_IcH (高度I)</label>
                <input v-model.number="pid.fIcH" type="number" class="pid-input" step="0.001" placeholder="0.015" />
              </div>
              <div class="pid-row">
                <label>F_KcHdot (垂向速度P)</label>
                <input v-model.number="pid.fKcHdot" type="number" class="pid-input" step="0.001" placeholder="0.5" />
              </div>
              <div class="pid-row">
                <label>F_IcHdot (垂向速度I)</label>
                <input v-model.number="pid.fIcHdot" type="number" class="pid-input" step="0.001" placeholder="0.05" />
              </div>
              <div class="pid-row">
                <label>F_KcAz (垂向加速度D)</label>
                <input v-model.number="pid.fKcAz" type="number" class="pid-input" step="0.001" placeholder="0.15" />
              </div>
            </div>

            <!-- 动力系统 -->
            <div class="pid-group">
              <h5 class="pid-group-title">动力系统 (Power System)</h5>
              <div class="pid-row">
                <label>F_IgRPM (电机转速I)</label>
                <input v-model.number="pid.fIgRPM" type="number" class="pid-input" step="0.001" placeholder="0.0" />
              </div>
              <div class="pid-row">
                <label>F_KgRPM (电机转速P)</label>
                <input v-model.number="pid.fKgRPM" type="number" class="pid-input" step="0.001" placeholder="0.01" />
              </div>
              <div class="pid-row">
                <label>F_Scale_factor (缩放因子)</label>
                <input v-model.number="pid.fScale_factor" type="number" class="pid-input" step="0.001" placeholder="1.0" />
              </div>
            </div>

            <!-- 自动控制参数 -->
            <div class="pid-group">
              <h5 class="pid-group-title">自动控制参数 (Auto Control)</h5>
              <div class="pid-row">
                <label>XaccLMT (X轴加限)</label>
                <input v-model.number="pid.XaccLMT" type="number" class="pid-input" step="0.1" placeholder="0.0" />
              </div>
              <div class="pid-row">
                <label>YaccLMT (Y轴加限)</label>
                <input v-model.number="pid.YaccLMT" type="number" class="pid-input" step="0.1" placeholder="0.0" />
              </div>
              <div class="pid-row">
                <label>Hground (地面高度)</label>
                <input v-model.number="pid.Hground" type="number" class="pid-input" step="0.1" placeholder="0.0" />
              </div>
              <div class="pid-row">
                <label>AutoTakeoffHcmd</label>
                <input v-model.number="pid.AutoTakeoffHcmd" type="number" class="pid-input" step="0.1" placeholder="0.0" />
              </div>
            </div>
          </div>
          <div class="section-actions">
            <button class="action-btn apply" @click="writePids">应用PID参数</button>
          </div>
        </div>
      </div>

      <!-- LiDAR网络配置 -->
      <div class="params-group">
        <div class="section-header">
          <h4 class="section-title" @click="toggleSection('network')">
            <span class="section-icon" :class="{ expanded: expandedSections.network }">▼</span>
            LiDAR网络配置
          </h4>
          <button class="icon-btn refresh" @click="readLidarConfig" title="读取配置">↻</button>
        </div>
        
        <div v-show="expandedSections.network" class="params-content">
          <div class="config-grid">
            <div class="config-row">
              <label>目标IP (Host Address)</label>
              <input v-model="lidarConfig.host_address" type="text" class="config-input" placeholder="192.168.1.100" />
            </div>
            <div class="config-row">
              <label>组播地址 (Group Address)</label>
              <input v-model="lidarConfig.group_address" type="text" class="config-input" placeholder="239.255.0.1" />
            </div>
            <div class="config-row">
              <label>MSOP端口</label>
              <input v-model.number="lidarConfig.msop_port" type="number" class="config-input" placeholder="2368" />
            </div>
            <div class="config-row">
              <label>DIFOP端口</label>
              <input v-model.number="lidarConfig.difop_port" type="number" class="config-input" placeholder="2369" />
            </div>
            <div class="config-row">
              <label>LiDAR类型</label>
              <select v-model.number="lidarConfig.lidar_type" class="config-input">
                <option :value="32">LIVOX Mid-360</option>
                <option :value="64">LIVOX Avia</option>
                <option :value="128">LIVOX Mid-360 (双)</option>
              </select>
            </div>
            <div class="config-row switch-row">
              <label>使用LiDAR时钟</label>
              <label class="toggle-switch">
                <input type="checkbox" v-model="lidarConfig.use_lidar_clock" />
                <span class="slider"></span>
              </label>
            </div>
          </div>
          <div class="section-actions">
            <button class="action-btn apply" @click="writeLidarConfig">应用网络配置</button>
          </div>
        </div>
      </div>

      <!-- 系统参数配置 -->
      <div class="params-group">
        <div class="section-header">
          <h4 class="section-title" @click="toggleSection('system')">
            <span class="section-icon" :class="{ expanded: expandedSections.system }">▼</span>
            系统参数配置
          </h4>
          <button class="icon-btn refresh" @click="readSystemConfig" title="读取配置">↻</button>
        </div>
        
        <div v-show="expandedSections.system" class="params-content">
          <div class="config-grid">
            <div class="config-row">
              <label>最大速度 (m/s)</label>
              <input v-model.number="systemConfig.max_speed" type="number" class="config-input" step="0.1" placeholder="15.0" />
            </div>
            <div class="config-row">
              <label>最大高度 (m)</label>
              <input v-model.number="systemConfig.max_altitude" type="number" class="config-input" step="0.1" placeholder="120.0" />
            </div>
            <div class="config-row">
              <label>起飞准备时间 (s)</label>
              <input v-model.number="systemConfig.takeoff_prep_time" type="number" class="config-input" step="0.1" placeholder="5.0" />
            </div>
            <div class="config-row">
              <label>着陆下降速度 (m/s)</label>
              <input v-model.number="systemConfig.land_speed" type="number" class="config-input" step="0.1" placeholder="1.0" />
            </div>
            <div class="config-row switch-row">
              <label>运动补偿</label>
              <label class="toggle-switch">
                <input type="checkbox" v-model="systemConfig.motion_compensation" />
                <span class="slider"></span>
              </label>
            </div>
            <div class="config-row switch-row">
              <label>航点自动平滑</label>
              <label class="toggle-switch">
                <input type="checkbox" v-model="systemConfig.waypoint_smoothing" />
                <span class="slider"></span>
              </label>
            </div>
          </div>
          <div class="section-actions">
            <button class="action-btn apply" @click="writeSystemConfig">应用系统配置</button>
          </div>
        </div>
      </div>

      <!-- 滤波器参数配置 -->
      <div class="params-group">
        <div class="section-header">
          <h4 class="section-title" @click="toggleSection('filter')">
            <span class="section-icon" :class="{ expanded: expandedSections.filter }">▼</span>
            LiDAR滤波器配置
          </h4>
          <button class="icon-btn refresh" @click="readFilterConfig" title="读取配置">↻</button>
        </div>
        
        <div v-show="expandedSections.filter" class="params-content">
          <div class="config-grid">
            <div class="config-header">体素滤波</div>
            <div class="config-row">
              <label>体素大小 (m)</label>
              <input v-model.number="filterConfig.voxel_size" type="number" class="config-input" step="0.01" placeholder="0.1" />
            </div>
            <div class="config-row">
              <label>最小点数</label>
              <input v-model.number="filterConfig.min_points" type="number" class="config-input" placeholder="5" />
            </div>
            
            <div class="config-header sor-header">SOR异常值过滤</div>
            <div class="config-row">
              <label>平均距离均值 (m)</label>
              <input v-model.number="filterConfig.sor_mean" type="number" class="config-input" step="0.01" placeholder="0.1" />
            </div>
            <div class="config-row">
              <label>标准差倍数</label>
              <input v-model.number="filterConfig.sor_std" type="number" class="config-input" step="0.1" placeholder="1.5" />
            </div>
            
            <div class="config-header">聚类参数</div>
            <div class="config-row">
              <label>聚类半径 (m)</label>
              <input v-model.number="filterConfig.cluster_radius" type="number" class="config-input" step="0.01" placeholder="0.3" />
            </div>
            <div class="config-row">
              <label>最小聚类点数</label>
              <input v-model.number="filterConfig.min_cluster_size" type="number" class="config-input" placeholder="10" />
            </div>
          </div>
          <div class="section-actions">
            <button class="action-btn apply" @click="writeFilterConfig">应用滤波配置</button>
          </div>
        </div>
        </div>
      </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()
const connected = computed(() => droneStore.connected)

const expandedSections = ref({
  pid: true,
  network: true,
  system: true,
  filter: false
})

const toggleSection = (section) => {
  expandedSections.value[section] = !expandedSections.value[section]
}

// PID参数（完整30个参数，根据interface.h定义）
const pid = ref({
  // 1. Ail (7)
  fKaPHI: 0.5,        // 滚转姿态P系数
  fKaP: 0.2,         // 滚转姿态D系数
  fKaY: 0.143,       // 横向位置P系数
  fIaY: 0.005,       // 横向位置I系数
  fKaVy: 2.0,        // 横向速度P系数
  fIaVy: 0.4,        // 横向速度I系数
  fKaAy: 0.28,       // 横向加速度D系数

  // 2. Ele (7)
  fKeTHETA: 0.5,      // 俯仰姿态P系数
  fKeQ: 0.2,         // 俯仰姿态D系数
  fKeX: 0.201,        // 纵向位置P系数
  fIeX: 0.01,         // 纵向位置I系数
  fKeVx: 2.0,         // 纵向速度P系数
  fIeVx: 0.4,        // 纵向速度I系数
  fKeAx: 0.55,        // 纵向加速度D系数

  // 3. Rud (4)
  fKrR: 0.2,         // 偏航角速度P系数
  fIrR: 0.01,         // 偏航角速度I系数
  fKrAy: 0.1,        // 偏航加速度P系数
  fKrPSI: 1.0,        // 偏航角P系数

  // 4. H (5)
  fKcH: 0.36,         // 高度P系数
  fIcH: 0.015,        // 高度I系数
  fKcHdot: 0.5,       // 垂向速度P系数
  fIcHdot: 0.05,      // 垂向速度I系数
  fKcAz: 0.15,        // 垂向加速度D系数

  // 5. RPM (2)
  fIgRPM: 0.0,        // 电机转速I系数
  fKgRPM: 0.01,       // 电机转速P系数

  // 6. Scale (1)
  fScale_factor: 1.0,    // 缩放因子

  // 7. New Params (4)
  XaccLMT: 1.0,       // X轴加速度限制
  YaccLMT: 1.0,       // Y轴加速度限制
  Hground: 0.4,       // 地面高度
  AutoTakeoffHcmd: 10.0 // 自动起飞高度指令
})

// LiDAR网络配置
const lidarConfig = ref({
  host_address: '192.168.1.100',
  group_address: '239.255.0.1',
  msop_port: 2368,
  difop_port: 2369,
  lidar_type: 32,
  use_lidar_clock: false
})

// 系统参数配置
const systemConfig = ref({
  max_speed: 15.0,
  max_altitude: 120.0,
  takeoff_prep_time: 5.0,
  land_speed: 1.0,
  motion_compensation: true,
  waypoint_smoothing: true
})

// 滤波器配置
const filterConfig = ref({
  voxel_size: 0.1,
  min_points: 5,
  sor_mean: 0.1,
  sor_std: 1.5,
  cluster_radius: 0.3,
  min_cluster_size: 10
})

// PID操作
const readPids = () => {
  console.log('读取PID参数')
  droneStore.addLog('正在读取PID参数...', 'warning')
}

const writePids = () => {
  console.log('写入PID参数', pid.value)
  droneStore.sendCommand('set_pids', pid.value)
  droneStore.addLog('PID参数已更新', 'info')
}

// LiDAR网络配置操作
const readLidarConfig = () => {
  console.log('读取LiDAR网络配置')
  droneStore.addLog('正在读取LiDAR网络配置...', 'warning')
}

const writeLidarConfig = () => {
  console.log('写入LiDAR网络配置', lidarConfig.value)
  droneStore.sendCommand('set_lidar_network', lidarConfig.value)
  droneStore.addLog('LiDAR网络配置已更新', 'info')
}

// 系统参数配置操作
const readSystemConfig = () => {
  console.log('读取系统参数配置')
  droneStore.addLog('正在读取系统参数配置...', 'warning')
}

const writeSystemConfig = () => {
  console.log('写入系统参数配置', systemConfig.value)
  droneStore.sendCommand('set_system_config', systemConfig.value)
  droneStore.addLog('系统参数配置已更新', 'info')
}

// 滤波器配置操作
const readFilterConfig = () => {
  console.log('读取滤波器配置')
  droneStore.addLog('正在读取滤波器配置...', 'warning')
}

const writeFilterConfig = () => {
  console.log('写入滤波器配置', filterConfig.value)
  droneStore.sendCommand('set_filter_config', filterConfig.value)
  droneStore.addLog('滤波器配置已更新', 'info')
}

onMounted(() => {
  readPids()
  readLidarConfig()
  readSystemConfig()
  readFilterConfig()
})
</script>

<style scoped>
.params-panel {
  padding: 15px;
  max-height: 100vh;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  max-height: 100vh;
  min-height: 0;
}

.params-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.params-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #e91e63;
}

.params-sections {
}

.params-group {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  cursor: pointer;
  user-select: none;
}

.section-title {
  color: #e91e63;
  font-size: 13px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  display: inline-block;
  transition: transform 0.2s;
}

.section-icon.expanded {
  transform: rotate(180deg);
}

.params-content {
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.config-header,
.pid-group-title {
  color: #e91e63;
  font-size: 11px;
  font-weight: 600;
  margin: 12px 0 8px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pid-group-title {
  margin: 10px 0 6px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(233, 30, 99, 0.3);
}

.pid-group {
  background: rgba(20, 20, 20, 0.5);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}

.pid-groups {
  display: grid;
  gap: 10px;
}

.pid-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.pid-row label {
  color: #cccccc;
  font-size: 11px;
}

.pid-input {
  background: rgba(20, 20, 20, 0.8);
  border: 1px solid #444444;
  border-radius: 4px;
  color: #ffffff;
  padding: 4px 8px;
  font-size: 11px;
  width: 80px;
}

.config-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-row.switch-row {
  justify-content: flex-start;
  gap: 10px;
}

.config-row label {
  color: #cccccc;
  font-size: 11px;
}

.config-input {
  background: rgba(20, 20, 20, 0.8);
  border: 1px solid #444444;
  border-radius: 4px;
  color: #ffffff;
  padding: 6px 10px;
  font-size: 12px;
  width: 140px;
}

.config-input:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-btn.refresh {
  background: transparent;
  border: 1px solid #666;
  border-radius: 4px;
  color: #999;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.icon-btn.refresh:hover {
  background: #666;
  color: #fff;
}

.section-actions {
  display: flex;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.action-btn.apply {
  flex: 1;
  background: #e91e63;
  border: none;
  border-radius: 6px;
  color: #ffffff;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s;
}

.action-btn.apply:hover {
  background: #c2185b;
}

.action-btn.apply:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-disabled {
  opacity: 0.4;
  pointer-events: none;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #555555;
  transition: .3s;
  border-radius: 20px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 14px;
  width: 14px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

.toggle-switch input:checked + .slider {
  background-color: #e91e63;
}

.toggle-switch input:checked + .slider:before {
  transform: translateX(16px);
}
</style>