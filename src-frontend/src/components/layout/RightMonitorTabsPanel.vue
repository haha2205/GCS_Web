<template>
  <div class="monitor-tabs-panel" :class="{ collapsed: isCollapsed, maximized: isMaximized }">
    <!-- 标签页头部 + 最大化/最小化按钮 -->
    <div class="tabs-header">
      <div class="tabs-wrapper">
        <div 
            v-for="tab in tabs" 
            :key="tab.id"
            class="tab-item"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
        >
          <span class="tab-icon">{{ tab.icon }}</span>
          <span class="tab-label">{{ tab.label }}</span>
        </div>
      </div>
      
      <!-- 最大化/最小化按钮 -->
      <div class="panel-controls">
        <button
          class="control-btn"
          :class="{ 'active': isMaximized }"
          @click="toggleMaximize"
          title="最大化/还原"
        >
          <svg v-if="!isMaximized" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4h16v16H4z"/>
            <path d="M14 4h6v6"/>
            <path d="M4 10h6v10"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 8h8v8H8z"/>
            <path d="M4 4h4v4h-4zM16 4h4v4h-4zM4 16h4v4h-4zM16 16h4v4h-4z"/>
          </svg>
        </button>
        <button
          class="control-btn collapse-btn"
          @click="isCollapsed = !isCollapsed"
          :title="isCollapsed ? '展开' : '收起'"
        >
          <svg v-if="!isCollapsed" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 12h16"/>
            <path d="M12 4l-8 8h16z"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 12h16"/>
            <path d="M12 4l8 8H4z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 标签页内容 -->
    <div class="tabs-content" :class="{ minimized: isCollapsed }">
      <!-- 控制标签页 -->
      <div class="content-scroll control-tab" v-show="activeTab === 'control'">
          <!--电机输出曲线 -->
          <div class="control-charts-section">
            <EChartWrapper
              key="pwm-chart"
              title="PWM输出"
              unit="μs"
              :series="pwmSeries"
              :yMin="1000"
              :yMax="2000"
            />
          </div>
          
          <!-- PWM数值显示 -->
          <div class="monitor-section">
            <div class="section-title">电机PWM输出 (6旋翼)</div>
            <div class="pwm-display">
              <div class="pwm-item" v-for="(pwm, index) in selectedPwms" :key="index">
                <div class="pwm-label">M{{ index + 1 }}</div>
                <div class="pwm-value">{{ pwm.toFixed(0) }}</div>
              </div>
            </div>
          </div>

          <!-- 遥控输入 -->
          <div class="monitor-section">
            <div class="section-title">遥控输入</div>
            <div class="remote-control-display">
              <div class="control-item">
                <span class="control-label">滚转 Roll</span>
                <span class="control-value">{{ rcRoll }}</span>
              </div>
              <div class="control-item">
                <span class="control-label">俯仰 Pitch</span>
                <span class="control-value">{{ rcPitch }}</span>
              </div>
              <div class="control-item">
                <span class="control-label">偏航 Yaw</span>
                <span class="control-value">{{ rcYaw }}</span>
              </div>
              <div class="control-item">
                <span class="control-label">油门 Col</span>
                <span class="control-value">{{ rcCol }}</span>
              </div>
              <div class="control-item">
                <span class="control-label">模式 Switch</span>
                <span class="control-value status-badge" :class="rcSwitch ? 'active' : 'inactive'">
                  {{ rcSwitch ? '开启' : '关闭' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 电机参数 (ExtY_FCS_ESC_T) -->
          <div class="monitor-section">
            <div class="section-title">电机参数 (ESC)</div>
            <div class="esc-display">
              <div class="esc-item" v-for="index in 6" :key="index">
                <div class="esc-motor-label">M{{ index }}</div>
                <div class="esc-data-grid">
                  <div class="esc-data-item">
                    <span class="esc-data-label">误差</span>
                    <span class="esc-data-value error">{{ getEscErrorCount(index) }}</span>
                  </div>
                  <div class="esc-data-item">
                    <span class="esc-data-label">转速</span>
                    <span class="esc-data-value rpm">{{ getEscRPM(index) }}</span>
                  </div>
                  <div class="esc-data-item">
                    <span class="esc-data-label">功率</span>
                    <span class="esc-data-value power">{{ getEscPowerRating(index) }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 避障标志 -->
          <div class="monitor-section">
            <div class="section-title">避障状态</div>
            <div class="avoidance-display">
              <div class="status-item">
                <span class="status-label">雷达启用</span>
                <span class="status-value" :class="laserRadarEnabled ? 'active' : 'inactive'">
                  {{ laserRadarEnabled ? '启用' : '禁用' }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">避障模式</span>
                <span class="status-value" :class="avoidanceFlag ? 'active' : 'inactive'">
                  {{ avoidanceFlag ? '开启' : '关闭' }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">引导模式</span>
                <span class="status-value" :class="guideFlag ? 'active' : 'inactive'">
                  {{ guideFlag ? '引导中' : '未引导' }}
                </span>
              </div>
            </div>
          </div>
      </div>

      <!-- 导航标签页 -->
      <div class="content-scroll navigation-tab" v-show="activeTab === 'navigation'">
          <!-- 位置曲线 -->
          <div class="navigation-charts-section">
            <EChartWrapper
              key="attitude-chart"
              title="姿态角"
              unit="度"
              :series="attitudeSeries"
              :yMin="-45"
              :yMax="45"
            />
            
            <EChartWrapper
              key="velocity-chart"
              title="速度分量"
              unit="m/s"
              :series="velocitySeries"
              :yMin="-20"
              :yMax="20"
            />
            
            <EChartWrapper
              key="altitude-chart"
              title="高度变化"
              unit="m"
              :series="altitudeSeries"
              :yMin="0"
              :yMax="100"
            />
          </div>

          <!-- 基础导航信息 -->
          <div class="monitor-section">
            <div class="section-title">飞行状态</div>
            <div class="attitude-display">
              <div class="attitude-item">
                <span class="attitude-label">滚转角 φ (Roll)</span>
                <span class="attitude-value">{{ states_phi.toFixed(2) }}°</span>
              </div>
              <div class="attitude-item">
                <span class="attitude-label">俯仰角 θ (Pitch)</span>
                <span class="attitude-value">{{ states_theta.toFixed(2) }}°</span>
              </div>
              <div class="attitude-item">
                <span class="attitude-label">偏航角 ψ (Yaw)</span>
                <span class="attitude-value">{{ states_psi.toFixed(2) }}°</span>
              </div>
            </div>
          </div>

          <!-- 角速度信息 -->
          <div class="monitor-section">
            <div class="section-title">角速度</div>
            <div class="angular-display">
              <div class="angular-item">
                <span class="angular-label">p (rad/s)</span>
                <span class="angular-value">{{ states_p.toFixed(3) }}</span>
              </div>
              <div class="angular-item">
                <span class="angular-label">q (rad/s)</span>
                <span class="angular-value">{{ states_q.toFixed(3) }}</span>
              </div>
              <div class="angular-item">
                <span class="angular-label">r (rad/s)</span>
                <span class="angular-value">{{ states_r.toFixed(3) }}</span>
              </div>
            </div>
          </div>

          <!-- 位置信息 -->
          <div class="monitor-section">
            <div class="section-title">位置信息 (经纬度/高度)</div>
            <div class="position-display">
              <div class="position-item">
                <span class="position-label">纬度 Latitude</span>
                <span class="position-value">{{ states_lat.toFixed(6) }}°</span>
              </div>
              <div class="position-item">
                <span class="position-label">经度 Longitude</span>
                <span class="position-value">{{ states_lon.toFixed(6) }}°</span>
              </div>
              <div class="position-item">
                <span class="position-label">高度 Height</span>
                <span class="position-value">{{ states_height.toFixed(2) }} m</span>
              </div>
            </div>
          </div>

          <!-- GCS指令数据 (ExtY_FCS_DATAGCS_T) -->
          <div class="monitor-section">
            <div class="section-title">地面站指令 (GCS)</div>
            <div class="gcs-display">
              <div class="gcs-item">
                <span class="gcs-label">指令索引 CmdIdx</span>
                <span class="gcs-value">{{ gcs_CmdIdx }}</span>
              </div>
              <div class="gcs-item">
                <span class="gcs-label">任务编号 Mission</span>
                <span class="gcs-value">{{ gcs_Mission }}</span>
              </div>
              <div class="gcs-item">
                <span class="gcs-label">指令参数 Val</span>
                <span class="gcs-value">{{ gcs_Val.toFixed(3) }}</span>
              </div>
              <div class="gcs-item">
                <span class="gcs-label">通信状态 Status</span>
                <span class="gcs-value" :class="gcsFail ? 'error' : 'ok'">
                  {{ gcsFail ? '失败' : '正常' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 速度信息 -->
          <div class="monitor-section">
            <div class="section-title">速度信息 (机体坐标系)</div>
            <div class="speed-display">
              <div class="speed-item">
                <span class="speed-label">Vx (纵向) m/s</span>
                <span class="speed-value">{{ states_Vx_GS.toFixed(2) }}</span>
              </div>
              <div class="speed-item">
                <span class="speed-label">Vy (横向) m/s</span>
                <span class="speed-value">{{ states_Vy_GS.toFixed(2) }}</span>
              </div>
              <div class="speed-item">
                <span class="speed-label">Vz (垂向) m/s</span>
                <span class="speed-value">{{ states_Vz_GS.toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <!-- GNC参数 -->
          <div class="monitor-section">
            <div class="section-title">GNC控制参数</div>
            <div class="gnc-display">
              <div class="gnc-item">
                <span class="gnc-label">Vx指令</span>
                <span class="gnc-value">{{ GNCBus_CmdValue_Vx_cmd.toFixed(2) }}</span>
              </div>
              <div class="gnc-item">
                <span class="gnc-label">Vy指令</span>
                <span class="gnc-value">{{ GNCBus_CmdValue_Vy_cmd.toFixed(2) }}</span>
              </div>
              <div class="gnc-item">
                <span class="gnc-label">高度指令</span>
                <span class="gnc-value">{{ GNCBus_CmdValue_height_cmd.toFixed(2) }}</span>
              </div>
              <div class="gnc-item">
                <span class="gnc-label">偏航指令</span>
                <span class="gnc-value">{{ GNCBus_CmdValue_psi_cmd.toFixed(2) }}</span>
              </div>
            </div>
          </div>
      </div>

      <!-- 系统性能标签页（5维KPI+DSM录制） -->
      <div class="content-scroll system-tab" v-show="activeTab === 'system'">
          <!-- DSM录制控制区 -->
          <div class="dsm-recording-section">
            <div class="section-title">DSM数据录制</div>
            
            <!-- 录制状态显示 -->
            <div class="recording-status">
              <div class="status-indicator" :class="recordingStatusClass"></div>
              <span class="status-text">{{ recordingStatusText }}</span>
            </div>
            
            <!-- 录制控制按钮 -->
            <div class="recording-controls">
              <button
                class="control-btn start-btn"
                @click="handleStartRecording"
                :disabled="isRecording || !wsConnected"
              >
                <span class="btn-icon">●</span>
                开始录制
              </button>
              <button
                class="control-btn stop-btn"
                @click="handleStopRecording"
                :disabled="!isRecording"
              >
                <span class="btn-icon">■</span>
                停止录制
              </button>
            </div>
            
            <!-- 当前会话信息 -->
            <div v-if="currentSessionId" class="session-info">
              <div class="session-label">当前会话</div>
              <div class="session-id">{{ currentSessionId }}</div>
            </div>
          </div>

          <!-- 算力资源 -->
          <ComputingKPI
            :dimensionData="droneStore.kpiHistory.computing[0] || {}"
          />
          
          <!-- 通信资源 -->
          <CommunicationKPI
            :dimensionData="droneStore.kpiHistory.communication[0] || {}"
          />
          
          <!-- 能耗指标 -->
          <EnergyKPI
            :dimensionData="droneStore.kpiHistory.energy[0] || {}"
          />
          
          <!-- 任务效能 -->
          <MissionKPI
            :dimensionData="droneStore.kpiHistory.mission[0] || {}"
          />
          
          <!-- 飞行性能 -->
          <PerformanceKPI
            :dimensionData="droneStore.kpiHistory.performance[0] || {}"
          />
        </div>
      </div>

      <!-- 分析标签页（变量曲线分析）-->
      <div class="content-scroll analysis-tab" v-show="activeTab === 'analysis'">
        <AnalysisPanel />
      </div>
   </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import EChartWrapper from '@/components/monitor/EChartWrapper.vue'
import ComputingKPI from '@/components/monitor/ComputingKPI.vue'
import CommunicationKPI from '@/components/monitor/CommunicationKPI.vue'
import EnergyKPI from '@/components/monitor/EnergyKPI.vue'
import MissionKPI from '@/components/monitor/MissionKPI.vue'
import PerformanceKPI from '@/components/monitor/PerformanceKPI.vue'
import AnalysisPanel from '@/components/AnalysisPanel.vue'

const droneStore = useDroneStore()
const wsConnected = computed(() => droneStore.connected)

// 标签页配置
const tabs = [
  { id: 'control', label: '控制', icon: '🎮' },
  { id: 'navigation', label: '导航', icon: '🧭' },
  { id: 'system', label: '系统性能', icon: '📊' },
  { id: 'analysis', label: '分析', icon: '📈' }
]

const activeTab = ref('control')
const isMaximized = ref(false)
const isCollapsed = ref(false)

// 切换最大化/最小化
const toggleMaximize = () => {
  isMaximized.value = !isMaximized.value
}

// DSM录制状态 (使用Store中的状态)
const isRecording = computed(() => droneStore.dataRecording.enabled)
const currentSessionId = ref('')

// 录制状态显示
const recordingStatusText = computed(() => {
  if (!wsConnected.value) return '未连接'
  return isRecording.value ? '录制中...' : '未录制'
})

const recordingStatusClass = computed(() => {
  if (!wsConnected.value) return 'status-disconnected'
  return isRecording.value ? 'status-recording' : 'status-idle'
})

// 处理开始录制
const handleStartRecording = () => {
  if (!wsConnected.value) {
    alert('WebSocket未连接')
    return
  }
  
  const success = droneStore.startDSMRecording()
  if (success) {
    currentSessionId.value = generateSessionId()
  }
}

// 处理停止录制
const handleStopRecording = () => {
  const success = droneStore.stopDSMRecording()
  if (success) {
    console.log('录制已停止，会话ID:', currentSessionId.value)
  }
}

// 生成会话ID
const generateSessionId = () => {
  const now = new Date()
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '')
  const timeStr = now.toTimeString().slice(0, 8).replace(/:/g, '')
  return `session_${dateStr}_${timeStr}`
}

// 从store获取真实数据（基于ExtY_FCS_T数据结构）
const selectedPwms = computed(() => {
  // 六旋翼使用前6个PWM，但显示所有8个
  const allPwms = droneStore.pwms || []
  return allPwms.slice(0, 8)
})

// 遥控数据 (ExtY_FCS_DATAFUTABA_T)
const rcRoll = computed(() => droneStore.fcsData?.Tele_ftb_Roll ?? 0)
const rcPitch = computed(() => droneStore.fcsData?.Tele_ftb_Pitch ?? 0)
const rcYaw = computed(() => droneStore.fcsData?.Tele_ftb_Yaw ?? 0)
const rcCol = computed(() => droneStore.fcsData?.Tele_ftb_Col ?? 0)
const rcSwitch = computed(() => droneStore.fcsData?.Tele_ftb_Switch ?? 0)

// 避障标志 (ExtY_FCS_AVOIFLAG_T)
const laserRadarEnabled = computed(() => droneStore.avoiFlag?.AvoiFlag_LaserRadar_Enabled ?? false)
const avoidanceFlag = computed(() => droneStore.avoiFlag?.AvoiFlag_AvoidanceFlag ?? false)
const guideFlag = computed(() => droneStore.avoiFlag?.AvoiFlag_GuideFlag ?? false)

// 飞行状态 (ExtY_FCS_STATES_T)
// 注意：飞控数据通常为弧度，显示时转换为度
const rad2deg = (rad) => rad * 180.0 / Math.PI

const states_lat = computed(() => droneStore.fcsStates?.states_lat ?? 0)
const states_lon = computed(() => droneStore.fcsStates?.states_lon ?? 0)
const states_height = computed(() => droneStore.fcsStates?.states_height ?? 0)
const states_Vx_GS = computed(() => droneStore.fcsStates?.states_Vx_GS ?? 0)
const states_Vy_GS = computed(() => droneStore.fcsStates?.states_Vy_GS ?? 0)
const states_Vz_GS = computed(() => droneStore.fcsStates?.states_Vz_GS ?? 0)
const states_p = computed(() => droneStore.fcsStates?.states_p ?? 0)
const states_q = computed(() => droneStore.fcsStates?.states_q ?? 0)
const states_r = computed(() => droneStore.fcsStates?.states_r ?? 0)
const states_phi = computed(() => rad2deg(droneStore.fcsStates?.states_phi ?? 0))
const states_theta = computed(() => rad2deg(droneStore.fcsStates?.states_theta ?? 0))
const states_psi = computed(() => rad2deg(droneStore.fcsStates?.states_psi ?? 0))

// GNC数据 (ExtY_FCS_GNCBUS_T)
const GNCBus_CmdValue_Vx_cmd = computed(() => droneStore.gncBus?.GNCBus_CmdValue_Vx_cmd ?? 0)
const GNCBus_CmdValue_Vy_cmd = computed(() => droneStore.gncBus?.GNCBus_CmdValue_Vy_cmd ?? 0)
const GNCBus_CmdValue_height_cmd = computed(() => droneStore.gncBus?.GNCBus_CmdValue_height_cmd ?? 0)
const GNCBus_CmdValue_psi_cmd = computed(() => droneStore.gncBus?.GNCBus_CmdValue_psi_cmd ?? 0)

// GCS数据 (ExtY_FCS_DATAGCS_T)
const gcs_CmdIdx = computed(() => droneStore.gcsData?.Tele_GCS_CmdIdx ?? 0)
const gcs_Mission = computed(() => droneStore.gcsData?.Tele_GCS_Mission ?? 0)
const gcs_Val = computed(() => droneStore.gcsData?.Tele_GCS_Val ?? 0)
const gcsFail = computed(() => droneStore.gcsData?.Tele_GCS_com_GCS_fail ?? 0)

// ESC数据辅助函数
const getEscErrorCount = (index) => {
  const escData = droneStore.escData
  if (index === 1) return escData.esc1_error_count ?? 0
  if (index === 2) return escData.esc2_error_count ?? 0
  if (index === 3) return escData.esc3_error_count ?? 0
  if (index === 4) return escData.esc4_error_count ?? 0
  if (index === 5) return escData.esc5_error_count ?? 0
  if (index === 6) return escData.esc6_error_count ?? 0
  return 0
}

const getEscRPM = (index) => {
  const escData = droneStore.escData
  if (index === 1) return escData.esc1_rpm ?? 0
  if (index === 2) return escData.esc2_rpm ?? 0
  if (index === 3) return escData.esc3_rpm ?? 0
  if (index === 4) return escData.esc4_rpm ?? 0
  if (index === 5) return escData.esc5_rpm ?? 0
  if (index === 6) return escData.esc6_rpm ?? 0
  return 0
}

const getEscPowerRating = (index) => {
  const escData = droneStore.escData
  if (index === 1) return escData.esc1_power_rating_pct ?? 0
  if (index === 2) return escData.esc2_power_rating_pct ?? 0
  if (index === 3) return escData.esc3_power_rating_pct ?? 0
  if (index === 4) return escData.esc4_power_rating_pct ?? 0
  if (index === 5) return escData.esc5_power_rating_pct ?? 0
  if (index === 6) return escData.esc6_power_rating_pct ?? 0
  return 0
}

// 图表数据系列（必须在watch之前定义）
const pwmSeries = computed(() => {
  // 从store历史数据获取PWM数据
  const pwm1Data = droneStore.history.pwm1?.map(item => item.value) || []
  const pwm2Data = droneStore.history.pwm2?.map(item => item.value) || []
  const pwm3Data = droneStore.history.pwm3?.map(item => item.value) || []
  const pwm4Data = droneStore.history.pwm4?.map(item => item.value) || []
  const pwm5Data = droneStore.history.pwm5?.map(item => item.value) || []
  const pwm6Data = droneStore.history.pwm6?.map(item => item.value) || []
  
  return [
    { name: 'M1', data: pwm1Data.slice(-100) || [1000], lineStyle: { color: '#ff6b6b' }, itemStyle: { color: '#ff6b6b' } },
    { name: 'M2', data: pwm2Data.slice(-100) || [1000], lineStyle: { color: '#4ecdc4' }, itemStyle: { color: '#4ecdc4' } },
    { name: 'M3', data: pwm3Data.slice(-100) || [1000], lineStyle: { color: '#45b7d1' }, itemStyle: { color: '#45b7d1' } },
    { name: 'M4', data: pwm4Data.slice(-100) || [1000], lineStyle: { color: '#96ceb4' }, itemStyle: { color: '#96ceb4' } },
    { name: 'M5', data: pwm5Data.slice(-100) || [1000], lineStyle: { color: '#ffa502' }, itemStyle: { color: '#ffa502' } },
    { name: 'M6', data: pwm6Data.slice(-100) || [1000], lineStyle: { color: '#ff6348' }, itemStyle: { color: '#ff6348' } }
  ]
})

const attitudeSeries = computed(() => {
  const rollData = droneStore.history.rollActual?.map(item => item.value) || []
  const pitchData = droneStore.history.pitchActual?.map(item => item.value) || []
  const yawData = droneStore.history.yawActual?.map(item => item.value) || []
  
  return [
    { name: 'Roll (φ)', data: rollData.length ? rollData : [0], lineStyle: { color: '#ff6b6b' }, itemStyle: { color: '#ff6b6b' } },
    { name: 'Pitch (θ)', data: pitchData.length ? pitchData : [0], lineStyle: { color: '#4ecdc4' }, itemStyle: { color: '#4ecdc4' } },
    { name: 'Yaw (ψ)', data: yawData.length ? yawData : [0], lineStyle: { color: '#45b7d1' }, itemStyle: { color: '#45b7d1' } }
  ]
})

const velocitySeries = computed(() => {
  const vxData = droneStore.history.velocityX?.map(item => item.value) || []
  const vyData = droneStore.history.velocityY?.map(item => item.value) || []
  const vzData = droneStore.history.velocityZ?.map(item => item.value) || []
  
  return [
    { name: 'Vx (纵向)', data: vxData.length ? vxData.slice(-100) : [0], lineStyle: { color: '#96ceb4' }, itemStyle: { color: '#96ceb4' } },
    { name: 'Vy (横向)', data: vyData.length ? vyData.slice(-100) : [0], lineStyle: { color: '#ffeaa7' }, itemStyle: { color: '#ffeaa7' } },
    { name: 'Vz (垂向)', data: vzData.length ? vzData.slice(-100) : [0], lineStyle: { color: '#dfe6e9' }, itemStyle: { color: '#dfe6e9' } }
  ]
})

const altitudeSeries = computed(() => {
  const altitudeData = droneStore.history.altitudeActual?.map(item => item.value) || []
  
  return [
    { name: '高度', data: altitudeData.length ? altitudeData.slice(-200) : [0], lineStyle: { color: '#74b9ff' }, itemStyle: { color: '#74b9ff' } }
  ]
})
</script>

<style scoped>
.monitor-tabs-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;  /* 关键修复：确保父容器有overflow: hidden，才能让子元素滚动 */
  background: linear-gradient(180deg, #0f0f0f 0%, #1a1a1a 100%);
  transition: width 0.3s ease, max-width 0.3s ease;
}

.monitor-tabs-panel.maximized {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  width: 100vw !important;
  max-width: none !important;
}

.monitor-tabs-panel.collapsed {
  width: 60px;
}

/* ==================== 标签页头部 ==================== */
.tabs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid #333;
  padding: 0;
  flex-shrink: 0; /* 固定头部高度 */
  height: 50px; /* 明确设置高度 */
}

.tabs-wrapper {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px; /* 垂直居中 */
  height: 100%; /* 占满父容器高度 */
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.3s ease;
  user-select: none;
  flex-shrink: 0;
}

.tab-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tab-item.active {
  border-bottom-color: #00bcd4;
  background: rgba(0, 188, 212, 0.1);
}

.tab-icon {
  font-size: 16px;
}

.tab-label {
  font-size: 13px;
  font-weight: 600;
  color: #888;
  transition: all 0.3s ease;
}

.tab-item.active .tab-label {
  color: #00bcd4;
}

.panel-controls {
  display: flex;
  gap: 6px;
  padding-right: 8px;
  flex-shrink: 0;
}

.control-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
  padding: 0;
  flex-shrink: 0;
}

.control-btn:hover {
  background: rgba(50, 136, 250, 0.2);
  color: #3288fa;
}

.control-btn.active {
  background: rgba(50, 136, 250, 0.3);
  color: #3288fa;
}

/* ==================== 标签页内容区域 - 关键修复 ==================== */
.tabs-content {
  flex: 1; /* 占据剩余空间 */
  min-height: 0; /* 关键：允许flex容器缩小和滚动 */
  overflow: hidden; /* 隐藏内容区域的直接溢出 */
  display: flex;
  flex-direction: column;
}

.tabs-content.minimized {
  display: none;
}

/* 滚动容器 - 关键修复（参考LeftConfigPanel） */
.content-scroll {
  flex: 1; /* 占据剩余空间 */
  overflow-y: auto; /* 始终启用垂直滚动 */
  overflow-x: hidden;
  padding: 16px;
  padding-right: 8px;
}

/* 优化滚动条样式 */
.content-scroll::-webkit-scrollbar {
  width: 8px;
}

.content-scroll::-webkit-scrollbar-track {
  background: rgba(30, 30, 30, 0.1);
  border-radius: 4px;
}

.content-scroll::-webkit-scrollbar-thumb {
  background: rgba(50, 136, 250, 0.5);
  border-radius: 4px;
  transition: background 0.2s;
}

.content-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(50, 136, 250, 0.8);
}

/* Firefox */
.content-scroll {
  scrollbar-width: thin;
  scrollbar-color: rgba(50, 136, 250, 0.5) rgba(30, 30, 30, 0.1);
}

/* ==================== 响应式调整 ==================== */
@media (max-height: 700px) {
  .content-scroll {
    padding: 12px;
  }
  
  .monitor-section {
    padding: 12px;
    margin-bottom: 12px;
  }
}

@media (max-height: 500px) {
  .content-scroll {
    padding: 8px;
  }
  
  .monitor-section {
    padding: 8px;
    margin-bottom: 8px;
  }
}

/* ==================== 监控面板通用样式 ==================== */
.monitor-section {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #333;
  flex-shrink: 0; /* 防止内容被压缩 */
  margin-bottom: 16px;
}

.monitor-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #00bcd4;
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ==================== 控制标签页 ==================== */
.control-charts-section {
  flex-shrink: 0;
  margin-bottom: 20px;
}

/* PWM显示 */
.pwm-display {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.pwm-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}

.pwm-label {
  font-size: 11px;
  color: #888;
  margin-bottom: 6px;
}

.pwm-value {
  font-size: 20px;
  font-weight: bold;
  color: #00bcd4;
  font-family: 'Courier New', monospace;
}

/* 遥控输入 */
.remote-control-display {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.control-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.control-item:last-child {
  border-bottom: none;
}

.control-label {
  font-size: 12px;
  color: #808080;
}

.control-value {
  font-size: 16px;
  font-weight: bold;
  color: #ffffff;
  font-family: 'Courier New', monospace;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.status-badge.active {
  background: rgba(46, 213, 115, 0.2);
  color: #2ed573;
}

.status-badge.inactive {
  background: rgba(255, 82, 82, 0.2);
  color: #ff5252;
}

/* ESC参数显示 */
.esc-display {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.esc-item {
  display: flex;
  flex-direction: column;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid rgba(0, 188, 212, 0.2);
}

.esc-motor-label {
  font-size: 12px;
  font-weight: bold;
  color: #00bcd4;
  margin-bottom: 8px;
  text-align: center;
}

.esc-data-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.esc-data-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.esc-data-label {
  font-size: 9px;
  color: #666;
  text-transform: uppercase;
}

.esc-data-value {
  font-size: 13px;
  font-weight: bold;
  color: #fff;
  font-family: 'Courier New', monospace;
}

.esc-data-value.error {
  color: #ff5252;
}

.esc-data-value.rpm {
  color: #4ecdc4;
}

.esc-data-value.power {
  color: #ffc107;
}

/* 避障显示 */
.avoidance-display {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}

.status-label {
  font-size: 12px;
  color: #888;
}

.status-value {
  font-size: 14px;
  font-weight: bold;
  padding: 4px 12px;
  border-radius: 4px;
}

.status-value.active {
  background: rgba(46, 213, 115, 0.2);
  color: #2ed573;
}

.status-value.inactive {
  background: rgba(255, 82, 82, 0.2);
  color: #ff5252;
}

/* ==================== 导航标签页 ==================== */
.navigation-charts-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

/* GCS数据显示 */
.gcs-display {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.gcs-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}

.gcs-value.error {
  color: #ff5252;
}

.gcs-value.ok {
  color: #2ed573;
}

/* 姿态、速度、位置、角速度显示 */
.attitude-display,
.angular-display,
.position-display,
.speed-display,
.gnc-display {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.gnc-display {
  grid-template-columns: repeat(2, 1fr);
}

.attitude-item,
.angular-item,
.position-item,
.speed-item,
.gnc-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}

.attitude-label,
.angular-label,
.position-label,
.speed-label,
.gnc-label {
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
}

.attitude-value,
.angular-value,
.position-value,
.speed-value,
.gnc-value {
  font-size: 18px;
  font-weight: bold;
  color: #00bcd4;
  font-family: 'Courier New', monospace;
}

/* ==================== 系统性能标签页 ==================== */
.system-tab {
  display: flex;
  flex-direction: column;
}

.dsm-recording-section {
  padding: 16px;
  background: rgba(0, 188, 212, 0.05);
  border: 1px solid rgba(0, 188, 212, 0.3);
  border-radius: 8px;
  flex-shrink: 0;
}

.recording-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.status-idle {
  background: #666;
  animation: none;
}

.status-recording {
  background: #ff5252;
}

.status-disconnected {
  background: #ff9800;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 12px;
  color: #b0b0b0;
}

.recording-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.btn-icon {
  font-size: 14px;
}

.session-info {
  padding: 10px;
  background: rgba(0, 188, 212, 0.1);
  border-radius: 6px;
}

.session-label {
  font-size: 10px;
  color: #00bcd4;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.session-id {
  font-size: 12px;
  color: #ffffff;
  font-family: 'Courier New', monospace;
  word-break: break-all;
}
</style>