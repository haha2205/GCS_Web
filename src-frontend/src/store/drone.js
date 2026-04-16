/**
 * Pinia Store - 无人机状态管理（核心通信版）
 */
import { defineStore } from 'pinia'
import backend, { isBackendUnavailableError } from '@/api/backend'
import { buildApiUrl, clearBackendBaseUrlCache, getBackendBaseUrl, resolveBackendBaseUrl } from '@/api/backend'
import { useWebSocket } from '@/composables/useWebSocket'

let wsInstance = null

function getWebSocketUrl() {
  const backendBaseUrl = getBackendBaseUrl()

  try {
    const backendUrl = new URL(backendBaseUrl)
    backendUrl.protocol = backendUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    backendUrl.pathname = '/ws/drone'
    backendUrl.search = ''
    backendUrl.hash = ''
    return backendUrl.toString()
  } catch (error) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.hostname || 'localhost'
    return `${protocol}://${host}:8000/ws/drone`
  }
}

function buildTimedSeries() {
  return [{ value: 0, timestamp: Date.now() }]
}

function buildHistoryState() {
  return {
    rollTarget: buildTimedSeries(),
    rollActual: buildTimedSeries(),
    pitchTarget: buildTimedSeries(),
    pitchActual: buildTimedSeries(),
    yawTarget: buildTimedSeries(),
    yawActual: buildTimedSeries(),
    speedTarget: buildTimedSeries(),
    speedActual: buildTimedSeries(),
    altitudeTarget: buildTimedSeries(),
    altitudeActual: buildTimedSeries(),
    controlU1: buildTimedSeries(),
    controlU2: buildTimedSeries(),
    controlU3: buildTimedSeries(),
    controlU4: buildTimedSeries(),
    velocityX: buildTimedSeries(),
    velocityY: buildTimedSeries(),
    velocityZ: buildTimedSeries(),
    angularRateP: buildTimedSeries(),
    angularRateQ: buildTimedSeries(),
    angularRateR: buildTimedSeries(),
    tokenRud: buildTimedSeries(),
    tokenAil: buildTimedSeries(),
    tokenEle: buildTimedSeries(),
    tokenCol: buildTimedSeries(),
    futabaRoll: buildTimedSeries(),
    futabaPitch: buildTimedSeries(),
    futabaYaw: buildTimedSeries(),
    pwm1: buildTimedSeries(),
    pwm2: buildTimedSeries(),
    pwm3: buildTimedSeries(),
    pwm4: buildTimedSeries(),
    pwm5: buildTimedSeries(),
    pwm6: buildTimedSeries(),
    pwm7: buildTimedSeries(),
    pwm8: buildTimedSeries(),
    escVoltage1: buildTimedSeries(),
    escVoltage2: buildTimedSeries(),
    escVoltage3: buildTimedSeries(),
    escVoltage4: buildTimedSeries(),
    escVoltage5: buildTimedSeries(),
    escVoltage6: buildTimedSeries(),
    escCurrent1: buildTimedSeries(),
    escCurrent2: buildTimedSeries(),
    escCurrent3: buildTimedSeries(),
    escCurrent4: buildTimedSeries(),
    escCurrent5: buildTimedSeries(),
    escCurrent6: buildTimedSeries(),
    escTemp1: buildTimedSeries(),
    escTemp2: buildTimedSeries(),
    escTemp3: buildTimedSeries(),
    escTemp4: buildTimedSeries(),
    escTemp5: buildTimedSeries(),
    escTemp6: buildTimedSeries(),
    escRpm1: buildTimedSeries(),
    escRpm2: buildTimedSeries(),
    escRpm3: buildTimedSeries(),
    escRpm4: buildTimedSeries(),
    escRpm5: buildTimedSeries(),
    escRpm6: buildTimedSeries(),
    escPower1: buildTimedSeries(),
    escPower2: buildTimedSeries(),
    escPower3: buildTimedSeries(),
    escPower4: buildTimedSeries(),
    escPower5: buildTimedSeries(),
    escPower6: buildTimedSeries()
  }
}

function buildMetricTrends() {
  return {
    pathDeviationM: buildTimedSeries(),
    pathErrorX: buildTimedSeries(),
    pathErrorY: buildTimedSeries(),
    pathErrorZ: buildTimedSeries(),
    obstacleCount: buildTimedSeries()
  }
}

function buildDefaultRecommendedArchitecture() {
  return {
    title: '最优架构方案',
    preset: 'native',
    paradigm: '联合式',
    description: '当前按论文最优预设展示模块到硬件节点的推荐部署，实时评测结果到达后可继续覆盖更新。',
    groupedAllocation: [
      {
        hardware: 'SoC_NPU',
        hardware_label: 'SoC NPU',
        modules: [
          { function: 'LF_Perception_Radar', function_label: '雷达感知' }
        ]
      },
      {
        hardware: 'SoC_ISP',
        hardware_label: 'SoC ISP',
        modules: [
          { function: 'LF_Perception_Camera', function_label: '相机感知' }
        ]
      },
      {
        hardware: 'SoC_CPU',
        hardware_label: 'SoC CPU',
        modules: [
          { function: 'LF_Path_Planning', function_label: '路径规划' },
          { function: 'LF_Comm_Telemery', function_label: '遥测通信' },
          { function: 'LF_Comm_MCU', function_label: 'MCU 通信' }
        ]
      },
      {
        hardware: 'MCU_GP4',
        hardware_label: 'MCU GP4',
        modules: [
          { function: 'LF_RC_Parser', function_label: '遥控解析' },
          { function: 'LF_INS_Parser', function_label: '惯导解析' }
        ]
      },
      {
        hardware: 'MCU_GP2',
        hardware_label: 'MCU GP2',
        modules: [
          { function: 'LF_Flight_Control', function_label: '飞控核心' },
          { function: 'LF_SoC_Adapter', function_label: 'SoC 适配' }
        ]
      },
      {
        hardware: 'MCU_GP3',
        hardware_label: 'MCU GP3',
        modules: [
          { function: 'LF_Motor_Driver', function_label: '电机驱动' }
        ]
      }
    ]
  }
}

export const useDroneStore = defineStore('drone', {
  state: () => ({
    connected: false,
    connecting: false,
    udpConnected: false,
    lastBackendMessage: null,

    pwms: [0, 0, 0, 0, 0, 0, 0, 0],
    motors: [0, 0, 0, 0, 0, 0],

    fcsStates: {
      states_lat: 0,
      states_lon: 0,
      states_height: 0,
      states_Vx_GS: 0,
      states_Vy_GS: 0,
      states_Vz_GS: 0,
      states_p: 0,
      states_q: 0,
      states_r: 0,
      states_phi: 0,
      states_theta: 0,
      states_psi: 0
    },

    fcsData: {
      Tele_ftb_Roll: 0,
      Tele_ftb_Pitch: 0,
      Tele_ftb_Yaw: 0,
      Tele_ftb_Col: 0,
      Tele_ftb_Switch: 0,
      Tele_ftb_com_Ftb_fail: 0
    },

    gncBus: {
      GNCBus_CmdValue_Vx_cmd: 0,
      GNCBus_CmdValue_Vy_cmd: 0,
      GNCBus_CmdValue_height_cmd: 0,
      GNCBus_CmdValue_psi_cmd: 0,
      GNCBus_TokenMode_rud_state: 0,
      GNCBus_TokenMode_ail_state: 0,
      GNCBus_TokenMode_ele_state: 0,
      GNCBus_TokenMode_col_state: 0
    },

    avoiFlag: {
      AvoiFlag_LaserRadar_Enabled: false,
      AvoiFlag_AvoidanceFlag: false,
      AvoiFlag_GuideFlag: false
    },

    systemStatus: {
      mode: 'DISARMED',
      battery: 0,
      voltage: 0,
      current: 0,
      gpsSatellites: 0,
      linkQuality: 0,
      laserRadarEnabled: false,
      avoidanceFlag: false,
      guideFlag: false
    },

    attitude: { roll: 0, pitch: 0, yaw: 0 },
    position: { lat: 0, lon: 0, alt: 0, relAlt: 0 },
    velocity: { x: 0, y: 0, z: 0 },
    angularVelocity: { p: 0, q: 0, r: 0 },

    controlLoop: {
      refRoll: 0,
      refPitch: 0,
      refYaw: 0,
      refAlt: 0,
      refVx: 0,
      refVy: 0,
      refVz: 0,
      estRoll: 0,
      estPitch: 0,
      estYaw: 0,
      estAlt: 0,
      estVx: 0,
      estVy: 0,
      estVz: 0,
      ctrlU1: 0,
      ctrlU2: 0,
      ctrlU3: 0,
      ctrlU4: 0
    },

    escData: {
      esc1_error_count: 0,
      esc2_error_count: 0,
      esc3_error_count: 0,
      esc4_error_count: 0,
      esc5_error_count: 0,
      esc6_error_count: 0,
      esc1_voltage: 0,
      esc2_voltage: 0,
      esc3_voltage: 0,
      esc4_voltage: 0,
      esc5_voltage: 0,
      esc6_voltage: 0,
      esc1_current: 0,
      esc2_current: 0,
      esc3_current: 0,
      esc4_current: 0,
      esc5_current: 0,
      esc6_current: 0,
      esc1_temperature: 0,
      esc2_temperature: 0,
      esc3_temperature: 0,
      esc4_temperature: 0,
      esc5_temperature: 0,
      esc6_temperature: 0,
      esc1_rpm: 0,
      esc2_rpm: 0,
      esc3_rpm: 0,
      esc4_rpm: 0,
      esc5_rpm: 0,
      esc6_rpm: 0,
      esc1_power_rating_pct: 0,
      esc2_power_rating_pct: 0,
      esc3_power_rating_pct: 0,
      esc4_power_rating_pct: 0,
      esc5_power_rating_pct: 0,
      esc6_power_rating_pct: 0
    },

    gcsData: {
      Tele_GCS_CmdIdx: 0,
      Tele_GCS_Mission: 0,
      Tele_GCS_Val: 0,
      Tele_GCS_com_GCS_fail: 0
    },

    selectedCmdIdx: 0,
    lastTelemetryCmdIdx: 0,
    latchedPlanningCmdIdx: 0,

    telemetryTimestamps: {
      flightState: null,
      gcsData: null
    },

    fcsParam: {
      paramId: 0,
      paramValue: 0,
      paramMin: 0,
      paramMax: 0
    },

    planningTelemetry: {
      seqId: 0,
      timestamp: 0,
      currentPosX: 0,
      currentPosY: 0,
      currentPosZ: 0,
      currentVel: 0,
      updateFlags: 0,
      status: 0,
      globalPathCount: 0,
      localTrajCount: 0,
      obstacleCount: 0
    },

    actualPose: {
      x: 0,
      y: 0,
      z: 0,
      pitch: 0,
      roll: 0,
      yaw: 0,
      timestamp: null,
      source: 'unknown'
    },

    actualFlightOrigin: {
      lat: null,
      lon: null,
      alt: null
    },

    trajectory: [],
    globalPath: [],
    globalPathLine: [],
    globalPathSignature: '',
    localTraj: [],
    obstacles: [],
    logs: [],
    systemLogs: [],
    lastLogSignature: '',
    lastLogAt: 0,
    history: buildHistoryState(),
    metricTrends: buildMetricTrends(),

    realtimeViews: {
      flightState: {
        latitude: 0,
        longitude: 0,
        height: 0,
        vx: 0,
        vy: 0,
        vz: 0,
        phi: 0,
        theta: 0,
        psi: 0,
        raw: {}
      },
      planningState: {
        planning_status: 0,
        global_path_count: 0,
        local_traj_count: 0,
        obstacle_count: 0,
        current_pos_x: 0,
        current_pos_y: 0,
        current_pos_z: 0
      },
      updatedAt: null
    },

    dataRecording: {
      enabled: false,
      recordingStartTime: null,
      recordCount: 0,
      recordFilePath: '',
      lastRecordTime: null,
      sessionId: '',
      totalBytes: 0,
      functionStats: []
    },

    onlineAnalysis: {
      enabled: false,
      baseUrl: '',
      timeoutMs: 0,
      lastUpdated: null,
      sessionId: '',
      ready: false,
      strictMeasuredReady: false,
      evidenceMode: 'waiting',
      compositeScore: null,
      domainScores: {
        perception: null,
        decision: null,
        control: null,
        communication: null,
        safety: null
      },
      availableChannels: [],
      missingRequiredChannels: [],
      missingMeasuredEnhancementChannels: [],
      recommendedArchitecture: buildDefaultRecommendedArchitecture(),
      history: {
        composite: buildTimedSeries()
      }
    },

    systemMode: 'REALTIME',

    config: {
      protocol: 'udp',
      hostIp: '192.168.16.13',
      hostPort: 30509,
      remoteIp: '192.168.16.116',
      sendOnlyPort: 18506,
      lidarSendPort: 18507,
      planningSendPort: 18510,
      planningRecvPort: 18511,
      logDirectory: '',
      autoRecord: false,
      logFormat: 'csv',
      logLevel: '1'
    }
  }),

  getters: {
    isConnected: (state) => state.connected,
    isUdpConnected: (state) => state.udpConnected,
    canSendCommands: (state) => state.connected && state.udpConnected,
    isConnectedText: (state) => (state.connected ? '已连接' : '未连接'),
    isArmed: (state) => state.systemStatus.mode !== 'DISARMED',
    modeText: (state) => {
      const modeMap = {
        DISARMED: '未解算',
        MANUAL: '手动',
        AUTO: '自动',
        GUIDED: '引导',
        RTL: '返航'
      }
      return modeMap[state.systemStatus.mode] || state.systemStatus.mode
    },
    lowBattery: (state) => state.systemStatus.voltage < 21.0,
    linkQualityText: (state) => {
      if (state.systemStatus.linkQuality > 80) return '优良'
      if (state.systemStatus.linkQuality > 50) return '良好'
      if (state.systemStatus.linkQuality > 30) return '一般'
      return '差'
    },
    selectedCommandIdx: (state) => state.selectedCmdIdx || 0,
    telemetryCommandIdx: (state) => state.lastTelemetryCmdIdx || state.gcsData.Tele_GCS_CmdIdx || 0,
    planningCommandIdx: (state) => state.latchedPlanningCmdIdx || state.selectedCmdIdx || state.lastTelemetryCmdIdx || state.gcsData.Tele_GCS_CmdIdx || 0,
    activeCommandIdx: (state) => state.selectedCmdIdx || state.lastTelemetryCmdIdx || state.gcsData.Tele_GCS_CmdIdx || 0,
    displaySystemLogs: (state) => state.systemLogs
  },

  actions: {
    _safeNumber(value, fallback = 0) {
      const parsed = Number(value)
      return Number.isFinite(parsed) ? parsed : fallback
    },

    _shouldPromoteSystemLog(message, level) {
      if (!message) {
        return false
      }

      if (level === 'error' || level === 'warning' || level === 'success') {
        return true
      }

      return /UDP|WebSocket|配置|指令|录制|规划|连接|断开|启动|停止|失败|错误/i.test(message)
    },

    _pushSystemLog(message, level, timestampMs) {
      const signature = `${level}:${message}`
      const lastSystemLog = this.systemLogs[this.systemLogs.length - 1]
      if (lastSystemLog && lastSystemLog.signature === signature && timestampMs - lastSystemLog.timestampMs < 1500) {
        return
      }

      this.systemLogs.push({
        id: timestampMs,
        timestampMs,
        time: new Date(timestampMs).toLocaleTimeString('zh-CN', { hour12: false }),
        level,
        signature,
        icon: level === 'error' ? '❌' : level === 'warning' ? '⚠' : level === 'success' ? '✓' : 'ℹ',
        message
      })

      if (this.systemLogs.length > 120) {
        this.systemLogs = this.systemLogs.slice(-120)
      }
    },

    setSelectedCommandIdx(cmdId, source = 'ui') {
      const normalizedCmdId = Math.max(0, parseInt(cmdId, 10) || 0)
      if (source === 'telemetry') {
        this.lastTelemetryCmdIdx = normalizedCmdId
        if (!this.latchedPlanningCmdIdx && normalizedCmdId > 0) {
          this.latchedPlanningCmdIdx = normalizedCmdId
        }
        if (!this.selectedCmdIdx && normalizedCmdId > 0) {
          this.selectedCmdIdx = normalizedCmdId
        }
        return
      }

      this.selectedCmdIdx = normalizedCmdId
      if (normalizedCmdId > 0) {
        this.latchedPlanningCmdIdx = normalizedCmdId
      }
    },

    _pushHistoryPoint(targetKey, value, timestamp = Date.now(), maxPoints = 500) {
      if (!this.history[targetKey]) {
        return
      }

      const numericValue = Number(value)
      if (!Number.isFinite(numericValue)) {
        return
      }

      this.history[targetKey].push({ value: numericValue, timestamp })
      if (this.history[targetKey].length > maxPoints) {
        this.history[targetKey] = this.history[targetKey].slice(-maxPoints)
      }
    },

    _pushMetricTrend(targetKey, value, timestamp = Date.now(), maxPoints = 160) {
      if (!this.metricTrends[targetKey]) {
        return
      }

      const numericValue = Number(value)
      if (!Number.isFinite(numericValue)) {
        return
      }

      this.metricTrends[targetKey].push({ value: numericValue, timestamp })
      if (this.metricTrends[targetKey].length > maxPoints) {
        this.metricTrends[targetKey] = this.metricTrends[targetKey].slice(-maxPoints)
      }
    },

    _pushOnlineAnalysisHistory(value, timestamp = Date.now(), maxPoints = 180) {
      const numericValue = Number(value)
      if (!Number.isFinite(numericValue)) {
        return
      }

      this.onlineAnalysis.history.composite.push({ value: numericValue, timestamp })
      if (this.onlineAnalysis.history.composite.length > maxPoints) {
        this.onlineAnalysis.history.composite = this.onlineAnalysis.history.composite.slice(-maxPoints)
      }
    },

    _extractPathPoint(point = {}) {
      return {
        x: this._safeNumber(point.x ?? point.pos_x ?? point.current_pos_x ?? point[0]),
        y: this._safeNumber(point.y ?? point.pos_y ?? point.current_pos_y ?? point[1]),
        z: this._safeNumber(point.z ?? point.pos_z ?? point.current_pos_z ?? point[2])
      }
    },

    _normalizePlanningPathPoints(path = []) {
      if (!Array.isArray(path)) {
        return []
      }

      return path
        .map((point) => this._extractPathPoint(point))
        .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z))
    },

    _buildPathSignature(path = []) {
      if (!Array.isArray(path) || !path.length) {
        return ''
      }

      return path
        .map((point) => {
          const normalized = this._extractPathPoint(point)
          return [normalized.x, normalized.y, normalized.z]
            .map((value) => this._safeNumber(value).toFixed(3))
            .join(',')
        })
        .join('|')
    },

    _captureGlobalPathLine(path = [], timestamp = Date.now()) {
      const normalizedPath = this._normalizePlanningPathPoints(path)
      if (!normalizedPath.length) {
        this.globalPathLine = []
        this.globalPathSignature = ''
        return
      }

      const signature = this._buildPathSignature(normalizedPath)
      if (signature === this.globalPathSignature && this.globalPathLine.length >= 2) {
        return
      }

      const actualPose = this.actualPose?.source === 'fcs_states'
        ? {
            x: this._safeNumber(this.actualPose.x),
            y: this._safeNumber(this.actualPose.y),
            z: this._safeNumber(this.actualPose.z)
          }
        : null

      const latestFlightPose = this._buildActualFlightPose(timestamp)
      const actualReference = actualPose || (latestFlightPose?.source === 'fcs_states'
        ? { x: latestFlightPose.x, y: latestFlightPose.y, z: latestFlightPose.z }
        : null)

      if (!actualReference) {
        this.globalPathLine = []
        return
      }

      const planningReference = this._getPlanningReferencePoint()
      const targetPlanningPoint = normalizedPath[0]
      const targetPoint = planningReference
        ? {
            x: targetPlanningPoint.x + (actualReference.x - planningReference.x),
            y: targetPlanningPoint.y + (actualReference.y - planningReference.y),
            z: targetPlanningPoint.z + (actualReference.z - planningReference.z)
          }
        : { ...targetPlanningPoint }

      this.globalPathLine = [
        { ...actualReference },
        targetPoint
      ]
      this.globalPathSignature = signature
    },

    _normalizePlanningObstacles(obstacles = []) {
      if (!Array.isArray(obstacles)) {
        return []
      }

      return obstacles.map((obstacle = {}) => {
        const center = obstacle.center || {}
        const size = obstacle.size || {}
        const velocity = obstacle.velocity || {}

        return {
          cx: this._safeNumber(obstacle.cx ?? center.x),
          cy: this._safeNumber(obstacle.cy ?? center.y),
          cz: this._safeNumber(obstacle.cz ?? center.z),
          sx: Math.max(0.1, this._safeNumber(obstacle.sx ?? size.x, 1)),
          sy: Math.max(0.1, this._safeNumber(obstacle.sy ?? size.y, 1)),
          sz: Math.max(0.1, this._safeNumber(obstacle.sz ?? size.z, 1)),
          vx: this._safeNumber(obstacle.vx ?? velocity.x),
          vy: this._safeNumber(obstacle.vy ?? velocity.y),
          vz: this._safeNumber(obstacle.vz ?? velocity.z)
        }
      })
    },

    _findNearestPathPoint(referencePoint, path = []) {
      if (!referencePoint || !Array.isArray(path) || !path.length) {
        return null
      }

      let nearestPoint = null
      let minDistance = Number.POSITIVE_INFINITY

      path.forEach((item) => {
        const candidate = this._extractPathPoint(item)
        const distance = Math.sqrt(
          (referencePoint.x - candidate.x) ** 2 +
          (referencePoint.y - candidate.y) ** 2 +
          (referencePoint.z - candidate.z) ** 2
        )
        if (distance < minDistance) {
          minDistance = distance
          nearestPoint = candidate
        }
      })

      return nearestPoint
    },

    _getActualFlightReferencePoint() {
      if (this.actualPose.timestamp === null) {
        return null
      }

      return {
        x: this._safeNumber(this.actualPose.x),
        y: this._safeNumber(this.actualPose.y),
        z: this._safeNumber(this.actualPose.z)
      }
    },

    _getPlanningReferencePoint() {
      const x = Number(this.planningTelemetry.currentPosX)
      const y = Number(this.planningTelemetry.currentPosY)
      const z = Number(this.planningTelemetry.currentPosZ)

      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
        return null
      }

      if (x === 0 && y === 0 && z === 0) {
        return null
      }

      return { x, y, z }
    },

    _getPlanningAlignmentOffset() {
      const actualPose = this.actualPose || {}
      const planningReference = this._getPlanningReferencePoint()

      if (actualPose.source !== 'fcs_states' || !planningReference) {
        return { x: 0, y: 0, z: 0, active: false }
      }

      if (!Number.isFinite(Number(actualPose.x)) || !Number.isFinite(Number(actualPose.y)) || !Number.isFinite(Number(actualPose.z))) {
        return { x: 0, y: 0, z: 0, active: false }
      }

      return {
        x: this._safeNumber(actualPose.x) - planningReference.x,
        y: this._safeNumber(actualPose.y) - planningReference.y,
        z: this._safeNumber(actualPose.z) - planningReference.z,
        active: true
      }
    },

    _alignPlanningPoint(point = {}) {
      const normalized = this._extractPathPoint(point)
      const offset = this._getPlanningAlignmentOffset()

      if (!offset.active) {
        return normalized
      }

      return {
        x: normalized.x + offset.x,
        y: normalized.y + offset.y,
        z: normalized.z + offset.z
      }
    },

    _getAlignedPlanningPath(path = []) {
      if (!Array.isArray(path)) {
        return []
      }

      return path.map((point) => this._alignPlanningPoint(point))
    },

    _hasValidGeoCoordinate(lat, lon) {
      const latitude = Number(lat)
      const longitude = Number(lon)
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        return false
      }
      if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
        return false
      }
      return !(Math.abs(latitude) < 1e-6 && Math.abs(longitude) < 1e-6)
    },

    _buildPlanningFallbackPose(timestamp = Date.now()) {
      const x = Number(this.planningTelemetry.currentPosX)
      const y = Number(this.planningTelemetry.currentPosY)
      const z = Number(this.planningTelemetry.currentPosZ)

      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
        return null
      }
      if (x === 0 && y === 0 && z === 0) {
        return null
      }

      return {
        x,
        y,
        z,
        pitch: this._safeNumber(this.attitude.pitch),
        roll: this._safeNumber(this.attitude.roll),
        yaw: this._safeNumber(this.attitude.yaw),
        timestamp,
        source: 'planning_telemetry'
      }
    },

    _projectGeoToLocal(lat, lon, alt = 0) {
      const latitude = Number(lat)
      const longitude = Number(lon)
      const altitude = this._safeNumber(alt)

      if (!this._hasValidGeoCoordinate(latitude, longitude)) {
        return null
      }

      if (this.actualFlightOrigin.lat === null || this.actualFlightOrigin.lon === null) {
        this.actualFlightOrigin = { lat: latitude, lon: longitude, alt: altitude }
      }

      const originLat = Number(this.actualFlightOrigin.lat)
      const originLon = Number(this.actualFlightOrigin.lon)
      const originAlt = this._safeNumber(this.actualFlightOrigin.alt, 0)
      const latScale = 111320
      const lonScale = 111320 * Math.cos(originLat * Math.PI / 180)

      return {
        x: (longitude - originLon) * lonScale,
        y: (latitude - originLat) * latScale,
        z: altitude - originAlt
      }
    },

    _buildActualFlightPose(timestamp = Date.now()) {
      const projected = this._projectGeoToLocal(
        this.fcsStates.states_lat,
        this.fcsStates.states_lon,
        this.fcsStates.states_height
      )

      if (projected) {
        return {
          ...projected,
          pitch: this._safeNumber(this.attitude.pitch),
          roll: this._safeNumber(this.attitude.roll),
          yaw: this._safeNumber(this.attitude.yaw),
          timestamp,
          source: 'fcs_states'
        }
      }

      return this._buildPlanningFallbackPose(timestamp)
    },

    _updateActualPoseFromTelemetry(timestamp = Date.now()) {
      const pose = this._buildActualFlightPose(timestamp)
      if (!pose) {
        return null
      }

      this.actualPose = pose
      if (pose.source === 'fcs_states') {
        this.addTrajectoryPoint(pose.x, pose.y, pose.z, timestamp)
      }
      return pose
    },

    _updatePathDeviationTrend(timestamp = Date.now()) {
      const referencePoint = this._getActualFlightReferencePoint()
      if (!referencePoint) {
        return
      }

      const alignedLocalTraj = this._getAlignedPlanningPath(this.localTraj)
      const alignedGlobalPath = this._getAlignedPlanningPath(this.globalPath)

      const targetPoint = this._findNearestPathPoint(referencePoint, alignedLocalTraj)
        || this._findNearestPathPoint(referencePoint, alignedGlobalPath)
      if (!targetPoint) {
        return
      }

      const errorX = targetPoint.x - referencePoint.x
      const errorY = targetPoint.y - referencePoint.y
      const errorZ = targetPoint.z - referencePoint.z
      const totalError = Math.sqrt(errorX ** 2 + errorY ** 2 + errorZ ** 2)

      this._pushMetricTrend('pathErrorX', errorX, timestamp)
      this._pushMetricTrend('pathErrorY', errorY, timestamp)
      this._pushMetricTrend('pathErrorZ', errorZ, timestamp)
      this._pushMetricTrend('pathDeviationM', totalError, timestamp)
    },

    initWebSocket() {
      if (wsInstance && wsInstance.connected?.value) {
        this.connected = true
        this.connecting = false
        return
      }

      if (wsInstance) {
        wsInstance.cleanup()
        wsInstance = null
      }

      wsInstance = useWebSocket(getWebSocketUrl())

      wsInstance.onOpen(() => {
        this.connected = true
        this.connecting = false
        this.addLog('WebSocket 连接已建立', 'info')
      })

      wsInstance.onClose(() => {
        this.connected = false
        this.connecting = false
        clearBackendBaseUrlCache()
        this.telemetryTimestamps.flightState = null
        this.telemetryTimestamps.gcsData = null
        this.addLog('WebSocket 连接已断开', 'warning')
      })

      wsInstance.onError((error) => {
        this.connecting = false
        const errorText = error?.message || error?.type || '连接异常'
        this.addLog(`WebSocket 错误: ${errorText}`, 'error')
      })

      wsInstance.onMessage((message) => {
        this.handleMessage(message)
      })

      wsInstance.connect()
    },

    disconnect() {
      if (wsInstance) {
        wsInstance.cleanup()
        wsInstance = null
      }
      this.connected = false
      this.connecting = false
      this.telemetryTimestamps.flightState = null
      this.telemetryTimestamps.gcsData = null
    },

    async connect() {
      if (this.connected || this.connecting) {
        return
      }

      this.connecting = true
      try {
        await resolveBackendBaseUrl(true)
        this.initWebSocket()
      } catch (error) {
        this.connecting = false
        this.addLog(`连接失败: ${error.message}`, 'error')
      }
    },

    handleMessage(message) {
      try {
        const data = typeof message === 'string' ? JSON.parse(message) : message
        this.lastBackendMessage = data

        if (data.type === 'udp_data') {
          const inner = data.data || {}
          const innerType = inner.type || 'unknown'
          const innerData = inner.data || {}
          this._handleUdpInnerMessage(innerType, innerData)
          return
        }

        switch (data.type) {
          case 'online_analysis_config':
            this.updateOnlineAnalysisConfig(data.data || {})
            break
          case 'online_analysis_status':
            this.updateOnlineAnalysisStatus(data)
            break
          case 'recording_status':
            this.applyRecordingStatus(data)
            break
          case 'udp_status_change':
            {
              const nextUdpConnected = data.status === 'connected'
              const udpStateChanged = this.udpConnected !== nextUdpConnected
              this.udpConnected = nextUdpConnected
              if (udpStateChanged) {
                this.addLog(`UDP链路${this.udpConnected ? '已连接' : '已断开'}`, this.udpConnected ? 'success' : 'warning')
              }
            }
            break
          case 'config_update':
            if (data.config_type === 'connection' && data.data) {
              this.updateConfig(data.data)
            }
            break
          case 'command_response':
            this.handleCommandResponse(data)
            break
          case 'log':
            this.addLog(data.message, data.level)
            break
          case 'fcs_states':
          case 'fcs_pwms':
          case 'fcs_datactrl':
          case 'fcs_gncbus':
          case 'avoiflag':
          case 'fcs_datafutaba':
          case 'fcs_esc':
          case 'fcs_datagcs':
          case 'fcs_param':
          case 'planning_telemetry':
            this._handleUdpInnerMessage(data.type, data.data || {})
            break
          default:
            break
        }
      } catch (error) {
        console.error('处理消息失败:', error)
      }
    },

    updateOnlineAnalysisConfig(payload = {}) {
      this.onlineAnalysis.enabled = !!payload.enabled
      this.onlineAnalysis.baseUrl = payload.base_url || ''
      this.onlineAnalysis.timeoutMs = Number(payload.timeout_ms || 0)
    },

    updateOnlineAnalysisStatus(payload = {}) {
      const timestamp = Number(payload.timestamp || Date.now())
      const scores = payload.scores || {}
      const domainScores = scores.domain_scores || {}
      const dependencyAudit = payload.dependency_audit || {}
      const recommendedArchitecture = payload.recommended_architecture || {}

      this.onlineAnalysis.lastUpdated = timestamp
      this.onlineAnalysis.sessionId = payload.session_id || ''
      this.onlineAnalysis.ready = !!payload.ready_for_live_scoring
      this.onlineAnalysis.strictMeasuredReady = !!payload.strict_measured_ready
      this.onlineAnalysis.evidenceMode = scores.evidence_mode || 'waiting'
      this.onlineAnalysis.compositeScore = Number.isFinite(Number(scores.composite_score)) ? Number(scores.composite_score) : null
      this.onlineAnalysis.domainScores = {
        perception: Number.isFinite(Number(domainScores.perception)) ? Number(domainScores.perception) : null,
        decision: Number.isFinite(Number(domainScores.decision)) ? Number(domainScores.decision) : null,
        control: Number.isFinite(Number(domainScores.control)) ? Number(domainScores.control) : null,
        communication: Number.isFinite(Number(domainScores.communication)) ? Number(domainScores.communication) : null,
        safety: Number.isFinite(Number(domainScores.safety)) ? Number(domainScores.safety) : null
      }
      this.onlineAnalysis.availableChannels = dependencyAudit.available_channels || []
      this.onlineAnalysis.missingRequiredChannels = dependencyAudit.missing_required_channels || []
      this.onlineAnalysis.missingMeasuredEnhancementChannels = dependencyAudit.missing_measured_enhancement_channels || []
      this.onlineAnalysis.recommendedArchitecture = {
        title: recommendedArchitecture.title || '',
        preset: recommendedArchitecture.preset || '',
        paradigm: recommendedArchitecture.paradigm || '',
        description: recommendedArchitecture.description || '',
        groupedAllocation: recommendedArchitecture.grouped_allocation || []
      }

      if (this.onlineAnalysis.compositeScore !== null) {
        this._pushOnlineAnalysisHistory(this.onlineAnalysis.compositeScore, timestamp)
      }
    },

    _handleUdpInnerMessage(messageType, payload) {
      switch (messageType) {
        case 'fcs_states':
          this.updateFlightState(payload)
          break
        case 'fcs_pwms':
          this.updateMotorPWMs(payload)
          this.addHistoryData('pwmData', payload)
          break
        case 'fcs_datactrl':
          this.updateControlLoop(payload)
          break
        case 'fcs_gncbus':
          this.updateGNCBus(payload)
          break
        case 'avoiflag':
          this.updateAvoiFlag(payload)
          break
        case 'fcs_datafutaba':
          this.updateFCSData(payload)
          break
        case 'fcs_esc':
          this.updateESCData(payload)
          break
        case 'fcs_datagcs':
          this.updateGCSData(payload)
          break
        case 'fcs_param':
          this.updateFCSParam(payload)
          break
        case 'planning_telemetry':
          this.updatePlanningTelemetry(payload)
          break
        case 'system_status':
          this.updateSystemStatus(payload)
          break
        default:
          break
      }
    },

    updateFlightState(data) {
      const timestamp = Date.now()
      this.telemetryTimestamps.flightState = timestamp

      if (data.states_lat !== undefined) {
        this.fcsStates.states_lat = parseFloat(data.states_lat)
        this.position.lat = parseFloat(data.states_lat)
      }
      if (data.states_lon !== undefined) {
        this.fcsStates.states_lon = parseFloat(data.states_lon)
        this.position.lon = parseFloat(data.states_lon)
      }
      if (data.states_height !== undefined) {
        this.fcsStates.states_height = parseFloat(data.states_height)
        this.position.alt = parseFloat(data.states_height)
        this.position.relAlt = parseFloat(data.states_height)
      }
      if (data.states_Vx_GS !== undefined) {
        this.fcsStates.states_Vx_GS = parseFloat(data.states_Vx_GS)
        this.velocity.x = parseFloat(data.states_Vx_GS)
      }
      if (data.states_Vy_GS !== undefined) {
        this.fcsStates.states_Vy_GS = parseFloat(data.states_Vy_GS)
        this.velocity.y = parseFloat(data.states_Vy_GS)
      }
      if (data.states_Vz_GS !== undefined) {
        this.fcsStates.states_Vz_GS = parseFloat(data.states_Vz_GS)
        this.velocity.z = parseFloat(data.states_Vz_GS)
      }
      if (data.states_p !== undefined) {
        const p = this._safeNumber(data.states_p)
        this.fcsStates.states_p = p
        this.angularVelocity.p = p
      }
      if (data.states_q !== undefined) {
        const q = this._safeNumber(data.states_q)
        this.fcsStates.states_q = q
        this.angularVelocity.q = q
      }
      if (data.states_r !== undefined) {
        const r = this._safeNumber(data.states_r)
        this.fcsStates.states_r = r
        this.angularVelocity.r = r
      }
      if (data.states_phi !== undefined) {
        const phiDeg = this._safeNumber(data.states_phi)
        this.fcsStates.states_phi = phiDeg
        this.attitude.roll = phiDeg
      }
      if (data.states_theta !== undefined) {
        const thetaDeg = this._safeNumber(data.states_theta)
        this.fcsStates.states_theta = thetaDeg
        this.attitude.pitch = thetaDeg
      }
      if (data.states_psi !== undefined) {
        const psiDeg = this._safeNumber(data.states_psi)
        this.fcsStates.states_psi = psiDeg
        this.attitude.yaw = psiDeg
      }

      this.realtimeViews.flightState = {
        latitude: this.fcsStates.states_lat,
        longitude: this.fcsStates.states_lon,
        height: this.fcsStates.states_height,
        vx: this.fcsStates.states_Vx_GS,
        vy: this.fcsStates.states_Vy_GS,
        vz: this.fcsStates.states_Vz_GS,
        phi: this.attitude.roll,
        theta: this.attitude.pitch,
        psi: this.attitude.yaw,
        raw: { ...data }
      }
      this.realtimeViews.updatedAt = timestamp

      this.addHistoryData('flightState', data)
      this._updateActualPoseFromTelemetry(timestamp)
    },

    updateMotorPWMs(data) {
      let pwmArray = null

      if (Array.isArray(data)) {
        pwmArray = data
      } else if (Array.isArray(data?.pwms)) {
        pwmArray = data.pwms
      }

      if (pwmArray && pwmArray.length > 0) {
        this.pwms = pwmArray.map((pwm) => parseFloat(pwm))
        this.motors = pwmArray.slice(0, 6).map((pwm) => parseFloat(pwm))
      }
    },

    updateControlLoop(data) {
      const ail = data.ailInLoop || {}
      const ailOut = data.ailOutLoop || {}
      const ele = data.EleInLoop || {}
      const eleOut = data.eleOutLoop || {}
      const rud = data.rudInLoop || {}
      const rudOut = data.RudOutLoop || {}
      const col = data.colOutLoop || {}
      const colIn = data.colInLoop || {}

      const merged = {
        ref_p: data.ref_p ?? (ail.phi_var !== undefined ? ail.phi_var + (ail.delta_phi || 0) : undefined),
        ref_theta: data.ref_theta ?? (ele.theta_var !== undefined ? ele.theta_var + (ele.delta_theta || 0) : undefined),
        ref_psi: data.ref_psi ?? (rudOut.psi_dy !== undefined ? rudOut.psi_dy + (rudOut.psi_delta || 0) : undefined),
        ref_h: data.ref_h ?? (col.Hdot_var !== undefined ? col.Hdot_var + (col.H_delta || 0) : undefined),
        ref_vx: data.ref_vx ?? (eleOut.Vx_var !== undefined ? eleOut.Vx_var + (eleOut.Vx_delta || 0) : undefined),
        ref_vy: data.ref_vy ?? (ailOut.Vy_var !== undefined ? ailOut.Vy_var + (ailOut.Vy_delta || 0) : undefined),
        ref_vz: data.ref_vz,
        est_p: data.est_p ?? ail.phi_var,
        est_theta: data.est_theta ?? ele.theta_var,
        est_psi: data.est_psi ?? rud.R_var,
        est_h: data.est_h ?? col.Hdot_var,
        est_vx: data.est_vx ?? eleOut.Vx_var,
        est_vy: data.est_vy ?? ailOut.Vy_var,
        est_vz: data.est_vz,
        ctrl_u1: data.ctrl_u1 ?? ail.ail_law_out,
        ctrl_u2: data.ctrl_u2 ?? ele.ele_law_out,
        ctrl_u3: data.ctrl_u3 ?? rud.rud_law_out,
        ctrl_u4: data.ctrl_u4 ?? colIn.col_law_out
      }

      if (merged.ref_p !== undefined) this.controlLoop.refRoll = parseFloat(merged.ref_p)
      if (merged.ref_theta !== undefined) this.controlLoop.refPitch = parseFloat(merged.ref_theta)
      if (merged.ref_psi !== undefined) this.controlLoop.refYaw = parseFloat(merged.ref_psi)
      if (merged.ref_h !== undefined) this.controlLoop.refAlt = parseFloat(merged.ref_h)
      if (merged.ref_vx !== undefined) this.controlLoop.refVx = parseFloat(merged.ref_vx)
      if (merged.ref_vy !== undefined) this.controlLoop.refVy = parseFloat(merged.ref_vy)
      if (merged.ref_vz !== undefined) this.controlLoop.refVz = parseFloat(merged.ref_vz)
      if (merged.est_p !== undefined) this.controlLoop.estRoll = parseFloat(merged.est_p)
      if (merged.est_theta !== undefined) this.controlLoop.estPitch = parseFloat(merged.est_theta)
      if (merged.est_psi !== undefined) this.controlLoop.estYaw = parseFloat(merged.est_psi)
      if (merged.est_h !== undefined) this.controlLoop.estAlt = parseFloat(merged.est_h)
      if (merged.est_vx !== undefined) this.controlLoop.estVx = parseFloat(merged.est_vx)
      if (merged.est_vy !== undefined) this.controlLoop.estVy = parseFloat(merged.est_vy)
      if (merged.est_vz !== undefined) this.controlLoop.estVz = parseFloat(merged.est_vz)
      if (merged.ctrl_u1 !== undefined) this.controlLoop.ctrlU1 = parseFloat(merged.ctrl_u1)
      if (merged.ctrl_u2 !== undefined) this.controlLoop.ctrlU2 = parseFloat(merged.ctrl_u2)
      if (merged.ctrl_u3 !== undefined) this.controlLoop.ctrlU3 = parseFloat(merged.ctrl_u3)
      if (merged.ctrl_u4 !== undefined) this.controlLoop.ctrlU4 = parseFloat(merged.ctrl_u4)

      this.addHistoryData('controlLoop', merged)
    },

    updateGNCBus(data) {
      if (data.GNCBus_CmdValue_Vx_cmd !== undefined) this.gncBus.GNCBus_CmdValue_Vx_cmd = parseFloat(data.GNCBus_CmdValue_Vx_cmd)
      if (data.GNCBus_CmdValue_Vy_cmd !== undefined) this.gncBus.GNCBus_CmdValue_Vy_cmd = parseFloat(data.GNCBus_CmdValue_Vy_cmd)
      if (data.GNCBus_CmdValue_height_cmd !== undefined) this.gncBus.GNCBus_CmdValue_height_cmd = parseFloat(data.GNCBus_CmdValue_height_cmd)
      if (data.GNCBus_CmdValue_psi_cmd !== undefined) this.gncBus.GNCBus_CmdValue_psi_cmd = parseFloat(data.GNCBus_CmdValue_psi_cmd)
      if (data.GNCBus_TokenMode_rud_state !== undefined) this.gncBus.GNCBus_TokenMode_rud_state = parseInt(data.GNCBus_TokenMode_rud_state)
      if (data.GNCBus_TokenMode_ail_state !== undefined) this.gncBus.GNCBus_TokenMode_ail_state = parseInt(data.GNCBus_TokenMode_ail_state)
      if (data.GNCBus_TokenMode_ele_state !== undefined) this.gncBus.GNCBus_TokenMode_ele_state = parseInt(data.GNCBus_TokenMode_ele_state)
      if (data.GNCBus_TokenMode_col_state !== undefined) this.gncBus.GNCBus_TokenMode_col_state = parseInt(data.GNCBus_TokenMode_col_state)

      this.addHistoryData('gncBus', data)
      this._updatePathDeviationTrend(Date.now())
    },

    updateAvoiFlag(data) {
      if (data.AvoiFlag_LaserRadar_Enabled !== undefined) {
        this.avoiFlag.AvoiFlag_LaserRadar_Enabled = !!data.AvoiFlag_LaserRadar_Enabled
        this.systemStatus.laserRadarEnabled = !!data.AvoiFlag_LaserRadar_Enabled
      }
      if (data.AvoiFlag_AvoidanceFlag !== undefined) {
        this.avoiFlag.AvoiFlag_AvoidanceFlag = !!data.AvoiFlag_AvoidanceFlag
        this.systemStatus.avoidanceFlag = !!data.AvoiFlag_AvoidanceFlag
      }
      if (data.AvoiFlag_GuideFlag !== undefined) {
        this.avoiFlag.AvoiFlag_GuideFlag = !!data.AvoiFlag_GuideFlag
        this.systemStatus.guideFlag = !!data.AvoiFlag_GuideFlag
      }
    },

    updateFCSData(data) {
      if (data.Tele_ftb_Roll !== undefined) this.fcsData.Tele_ftb_Roll = parseFloat(data.Tele_ftb_Roll)
      if (data.Tele_ftb_Pitch !== undefined) this.fcsData.Tele_ftb_Pitch = parseFloat(data.Tele_ftb_Pitch)
      if (data.Tele_ftb_Yaw !== undefined) this.fcsData.Tele_ftb_Yaw = parseFloat(data.Tele_ftb_Yaw)
      if (data.Tele_ftb_Col !== undefined) this.fcsData.Tele_ftb_Col = parseFloat(data.Tele_ftb_Col)
      if (data.Tele_ftb_Switch !== undefined) this.fcsData.Tele_ftb_Switch = parseInt(data.Tele_ftb_Switch)
      if (data.Tele_ftb_com_Ftb_fail !== undefined) this.fcsData.Tele_ftb_com_Ftb_fail = parseInt(data.Tele_ftb_com_Ftb_fail)
      this.addHistoryData('fcsData', data)
    },

    updateESCData(data) {
      const intFields = ['error_count', 'rpm', 'power_rating_pct']
      const floatFields = ['voltage', 'current', 'temperature']
      const allFields = [...intFields, ...floatFields]

      for (let index = 1; index <= 6; index += 1) {
        allFields.forEach((field) => {
          const key = `esc${index}_${field}`
          if (data[key] !== undefined) {
            this.escData[key] = intFields.includes(field) ? parseInt(data[key]) : parseFloat(data[key])
          }
        })
      }

      this.addHistoryData('escData', data)
    },

    updateGCSData(data) {
      this.telemetryTimestamps.gcsData = Date.now()
      if (data.Tele_GCS_CmdIdx !== undefined) this.gcsData.Tele_GCS_CmdIdx = parseInt(data.Tele_GCS_CmdIdx)
      if (data.Tele_GCS_Mission !== undefined) this.gcsData.Tele_GCS_Mission = parseInt(data.Tele_GCS_Mission)
      if (data.Tele_GCS_Val !== undefined) this.gcsData.Tele_GCS_Val = parseFloat(data.Tele_GCS_Val)
      if (data.Tele_GCS_com_GCS_fail !== undefined) this.gcsData.Tele_GCS_com_GCS_fail = parseInt(data.Tele_GCS_com_GCS_fail)

      if (data.Tele_GCS_CmdIdx !== undefined) {
        this.setSelectedCommandIdx(data.Tele_GCS_CmdIdx, 'telemetry')
      }
    },

    updateFCSParam(data) {
      if (data.param_id !== undefined) this.fcsParam.paramId = parseInt(data.param_id)
      if (data.param_value !== undefined) this.fcsParam.paramValue = parseFloat(data.param_value)
      if (data.param_min !== undefined) this.fcsParam.paramMin = parseFloat(data.param_min)
      if (data.param_max !== undefined) this.fcsParam.paramMax = parseFloat(data.param_max)
    },

    updatePlanningTelemetry(data) {
      const timestamp = Date.now()
      const position = data.position || {}
      const currentPosX = data.current_pos_x ?? position.x
      const currentPosY = data.current_pos_y ?? position.y
      const currentPosZ = data.current_pos_z ?? position.z
      const globalPath = Array.isArray(data.global_path) ? this._normalizePlanningPathPoints(data.global_path) : null
      const localTraj = Array.isArray(data.local_traj)
        ? this._normalizePlanningPathPoints(data.local_traj)
        : (Array.isArray(data.local_path) ? this._normalizePlanningPathPoints(data.local_path) : null)
      const obstacles = Array.isArray(data.obstacles) ? this._normalizePlanningObstacles(data.obstacles) : null

      if (data.seq_id !== undefined) this.planningTelemetry.seqId = parseInt(data.seq_id)
      if (data.timestamp !== undefined) this.planningTelemetry.timestamp = parseInt(data.timestamp)
      if (currentPosX !== undefined) this.planningTelemetry.currentPosX = parseFloat(currentPosX)
      if (currentPosY !== undefined) this.planningTelemetry.currentPosY = parseFloat(currentPosY)
      if (currentPosZ !== undefined) this.planningTelemetry.currentPosZ = parseFloat(currentPosZ)
      if (data.current_vel !== undefined) this.planningTelemetry.currentVel = parseFloat(data.current_vel)
      if (data.update_flags !== undefined) this.planningTelemetry.updateFlags = parseInt(data.update_flags)
      if (data.status !== undefined) this.planningTelemetry.status = parseInt(data.status)
      if (data.global_path_count !== undefined) this.planningTelemetry.globalPathCount = parseInt(data.global_path_count)
      if (data.local_traj_count !== undefined) this.planningTelemetry.localTrajCount = parseInt(data.local_traj_count)
      if (data.obstacle_count !== undefined) this.planningTelemetry.obstacleCount = parseInt(data.obstacle_count)

      if (globalPath) {
        this.globalPath = globalPath
        this._captureGlobalPathLine(globalPath, timestamp)
      }
      if (localTraj) {
        this.localTraj = localTraj
      }
      if (obstacles) {
        this.obstacles = obstacles
      }

      this.realtimeViews.planningState = {
        planning_status: this.planningTelemetry.status,
        global_path_count: this.planningTelemetry.globalPathCount,
        local_traj_count: this.planningTelemetry.localTrajCount,
        obstacle_count: this.planningTelemetry.obstacleCount,
        current_pos_x: this.planningTelemetry.currentPosX,
        current_pos_y: this.planningTelemetry.currentPosY,
        current_pos_z: this.planningTelemetry.currentPosZ
      }
      this.realtimeViews.updatedAt = timestamp

      this._updateActualPoseFromTelemetry(timestamp)
      this._updatePathDeviationTrend(timestamp)
      this._pushMetricTrend('obstacleCount', this.planningTelemetry.obstacleCount, timestamp)
    },

    updateSystemStatus(data) {
      if (data.mode !== undefined) this.systemStatus.mode = data.mode
      if (data.battery !== undefined) this.systemStatus.battery = data.battery
      if (data.voltage !== undefined) this.systemStatus.voltage = data.voltage
      if (data.current !== undefined) this.systemStatus.current = data.current
      if (data.gpsSatellites !== undefined) this.systemStatus.gpsSatellites = data.gpsSatellites
      if (data.linkQuality !== undefined) this.systemStatus.linkQuality = data.linkQuality
    },

    applyRecordingStatus(payload) {
      const sessionInfo = payload?.session_info || {}
      const recordingData = payload?.data || {}

      this.dataRecording.enabled = payload?.is_active ?? !!recordingData.recording
      this.dataRecording.sessionId = payload?.session_id || sessionInfo.session_id || ''
      this.dataRecording.recordingStartTime = sessionInfo.start_time
        ? Math.round(sessionInfo.start_time * 1000)
        : (this.dataRecording.enabled ? this.dataRecording.recordingStartTime : null)
      this.dataRecording.recordFilePath = sessionInfo.data_directory || recordingData.output_dir || ''
      this.dataRecording.recordCount = sessionInfo.data_counters?.raw_records || 0
      this.dataRecording.totalBytes = sessionInfo.total_bytes || recordingData.bytes_written || 0
      this.dataRecording.functionStats = sessionInfo.func_stats || []
      this.dataRecording.lastRecordTime = Date.now()
    },

    async sendRemoteCommand(cmdId, cmdName) {
      if (!this.connected) {
        this.addLog('未连接到后端，无法发送指令', 'warning')
        return null
      }
      if (!this.udpConnected) {
        this.addLog('UDP未连接，指令不会发往机载端', 'warning')
        return null
      }
      this.setSelectedCommandIdx(cmdId, 'ui')
      return this.sendCommandREST('cmd_idx', { cmdId, name: cmdName })
    },

    async fetchRecordingStatus() {
      try {
        const status = await backend.recording.getStatus()
        this.applyRecordingStatus(status)
        return status
      } catch (error) {
        if (!isBackendUnavailableError(error)) {
          this.addLog(`获取录制状态失败: ${error.message}`, 'warning')
        }
        return null
      }
    },

    async fetchUdpStatus() {
      try {
        const status = await backend.udp.getStatus()
        this.udpConnected = !!status?.data?.connected
        return status
      } catch (error) {
        this.udpConnected = false
        if (!isBackendUnavailableError(error)) {
          this.addLog(`获取UDP状态失败: ${error.message}`, 'warning')
        }
        return null
      }
    },

    async startFullRecording(config = {}) {
      try {
        const response = await backend.recording.startRecording(config)
        this.applyRecordingStatus({
          is_active: true,
          session_id: response.session_id,
          session_info: response.session_info
        })
        this.addLog('开始录制', 'info')
        return response
      } catch (error) {
        this.addLog(`开始录制失败: ${error.message}`, 'error')
        throw error
      }
    },

    async stopFullRecording() {
      try {
        const response = await backend.recording.stopRecording()
        this.applyRecordingStatus({
          is_active: false,
          session_id: response.session_id,
          session_info: response.session_info
        })
        this.addLog('停止录制', 'info')
        return response
      } catch (error) {
        this.addLog(`停止录制失败: ${error.message}`, 'error')
        throw error
      }
    },

    addHistoryData(category, data) {
      const timestamp = Date.now()

      switch (category) {
        case 'flightState':
          this._pushHistoryPoint('rollActual', data.states_phi ?? this.attitude.roll, timestamp)
          this._pushHistoryPoint('pitchActual', data.states_theta ?? this.attitude.pitch, timestamp)
          this._pushHistoryPoint('yawActual', data.states_psi ?? this.attitude.yaw, timestamp)
          this._pushHistoryPoint('altitudeActual', data.states_height ?? this.position.alt, timestamp)
          this._pushHistoryPoint('velocityX', data.states_Vx_GS ?? this.velocity.x, timestamp)
          this._pushHistoryPoint('velocityY', data.states_Vy_GS ?? this.velocity.y, timestamp)
          this._pushHistoryPoint('velocityZ', data.states_Vz_GS ?? this.velocity.z, timestamp)
          this._pushHistoryPoint('angularRateP', data.states_p ?? this.angularVelocity.p, timestamp)
          this._pushHistoryPoint('angularRateQ', data.states_q ?? this.angularVelocity.q, timestamp)
          this._pushHistoryPoint('angularRateR', data.states_r ?? this.angularVelocity.r, timestamp)
          break
        case 'gncBus':
          this._pushHistoryPoint('tokenRud', data.GNCBus_TokenMode_rud_state ?? this.gncBus.GNCBus_TokenMode_rud_state, timestamp)
          this._pushHistoryPoint('tokenAil', data.GNCBus_TokenMode_ail_state ?? this.gncBus.GNCBus_TokenMode_ail_state, timestamp)
          this._pushHistoryPoint('tokenEle', data.GNCBus_TokenMode_ele_state ?? this.gncBus.GNCBus_TokenMode_ele_state, timestamp)
          this._pushHistoryPoint('tokenCol', data.GNCBus_TokenMode_col_state ?? this.gncBus.GNCBus_TokenMode_col_state, timestamp)
          break
        case 'fcsData':
          this._pushHistoryPoint('futabaRoll', data.Tele_ftb_Roll ?? this.fcsData.Tele_ftb_Roll, timestamp)
          this._pushHistoryPoint('futabaPitch', data.Tele_ftb_Pitch ?? this.fcsData.Tele_ftb_Pitch, timestamp)
          this._pushHistoryPoint('futabaYaw', data.Tele_ftb_Yaw ?? this.fcsData.Tele_ftb_Yaw, timestamp)
          break
        case 'controlLoop':
          this._pushHistoryPoint('rollTarget', data.ref_p, timestamp)
          this._pushHistoryPoint('rollActual', data.est_p, timestamp)
          this._pushHistoryPoint('pitchTarget', data.ref_theta, timestamp)
          this._pushHistoryPoint('pitchActual', data.est_theta, timestamp)
          this._pushHistoryPoint('yawTarget', data.ref_psi, timestamp)
          this._pushHistoryPoint('yawActual', data.est_psi, timestamp)
          this._pushHistoryPoint('altitudeTarget', data.ref_h, timestamp)
          this._pushHistoryPoint('altitudeActual', data.est_h, timestamp)
          this._pushHistoryPoint('speedTarget', data.ref_vx, timestamp)
          this._pushHistoryPoint('speedActual', data.est_vx, timestamp)
          this._pushHistoryPoint('controlU1', data.ctrl_u1, timestamp)
          this._pushHistoryPoint('controlU2', data.ctrl_u2, timestamp)
          this._pushHistoryPoint('controlU3', data.ctrl_u3, timestamp)
          this._pushHistoryPoint('controlU4', data.ctrl_u4, timestamp)
          break
        case 'pwmData': {
          const pwmArray = Array.isArray(data) ? data : data?.pwms || []
          pwmArray.forEach((pwm, index) => {
            this._pushHistoryPoint(`pwm${index + 1}`, pwm, timestamp)
          })
          break
        }
        case 'escData': {
          const fieldMap = [
            ['voltage', 'escVoltage'],
            ['current', 'escCurrent'],
            ['temperature', 'escTemp'],
            ['rpm', 'escRpm'],
            ['power_rating_pct', 'escPower']
          ]
          fieldMap.forEach(([sourceSuffix, targetPrefix]) => {
            for (let index = 1; index <= 6; index += 1) {
              const value = data[`esc${index}_${sourceSuffix}`] ?? this.escData[`esc${index}_${sourceSuffix}`]
              this._pushHistoryPoint(`${targetPrefix}${index}`, value, timestamp)
            }
          })
          break
        }
        default:
          break
      }
    },

    _formatCommandDetails(type, params) {
      if (!params) return ''
      if (type === 'cmd_idx') {
        return `[${params.cmdId}: ${params.name || ''}]`
      }
      if (type === 'cmd_mission') {
        return `[${params.cmd_mission}: ${params.value}]`
      }
      if (type === 'set_pids') {
        return `[${Object.keys(params).length}个参数]`
      }
      return ''
    },

    async sendCommandREST(type, payload) {
      try {
        if (type === 'cmd_idx' && payload?.cmdId !== undefined) {
          this.setSelectedCommandIdx(payload.cmdId, 'ui')
        }

        if (type === 'gcs_command') {
          const requestedCmdId = Math.max(0, parseInt(payload?.cmdId, 10) || 0)
          const latchedCmdId = Math.max(0, parseInt(this.latchedPlanningCmdIdx, 10) || 0)
          if (requestedCmdId <= 0 && latchedCmdId > 0) {
            payload = {
              ...payload,
              cmdId: latchedCmdId
            }
          }
        }

        const response = await fetch(buildApiUrl('/api/command'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type, params: payload })
        })
        const result = await response.json()
        this.addLog(`指令发送: ${type} ${this._formatCommandDetails(type, payload)} - ${result.status || 'unknown'}`, 'info')
        return result
      } catch (error) {
        this.addLog(`发送指令失败: ${error.message}`, 'error')
        return null
      }
    },

    sendCommand(type, payload) {
      if (!this.connected || !wsInstance) {
        this.addLog('未连接到后端，无法发送指令', 'warning')
        return false
      }

      const message = {
        type: 'command',
        command: type,
        params: payload,
        timestamp: Date.now()
      }

      try {
        wsInstance.send(JSON.stringify(message))
        this.addLog(`指令发送: ${type} ${this._formatCommandDetails(type, payload)}`, 'info')
        return true
      } catch (error) {
        this.addLog(`发送指令失败: ${error.message}`, 'error')
        return false
      }
    },

    handleCommandResponse(data) {
      this.addLog(`指令响应: ${data.command} - ${data.status}`, 'info')
    },

    addLog(message, level = 'info') {
      const timestampMs = Date.now()
      const signature = `${level}:${message}`
      if (signature === this.lastLogSignature && timestampMs - this.lastLogAt < 1200) {
        return
      }

      this.lastLogSignature = signature
      this.lastLogAt = timestampMs

      this.logs.push({
        id: timestampMs,
        message,
        level,
        timestamp: new Date(timestampMs).toLocaleString()
      })
      if (this.logs.length > 500) {
        this.logs.shift()
      }

      if (this._shouldPromoteSystemLog(message, level)) {
        this._pushSystemLog(message, level, timestampMs)
      }
    },

    updateConfig(config) {
      const normalizedConfig = { ...config }
      if (Object.prototype.hasOwnProperty.call(normalizedConfig, 'listenAddress')) {
        normalizedConfig.hostIp = normalizedConfig.listenAddress
      }
      this.config = { ...this.config, ...normalizedConfig }
    },

    addTrajectoryPoint(x, y, z, timestamp = Date.now()) {
      const lastPoint = this.trajectory[this.trajectory.length - 1]
      if (lastPoint) {
        const distance = Math.sqrt((x - lastPoint.x) ** 2 + (y - lastPoint.y) ** 2 + (z - lastPoint.z) ** 2)
        if (distance < 0.1) {
          return
        }
      }

      this.trajectory.push({ x, y, z, timestamp })
      if (this.trajectory.length > 1000) {
        this.trajectory.shift()
      }
    },

    clearLogs() {
      this.logs = []
      this.systemLogs = []
      this.lastLogSignature = ''
      this.lastLogAt = 0
    },

    clearTrajectory() {
      this.trajectory = []
      this.globalPathLine = []
      this.globalPathSignature = ''
      this.actualPose = {
        x: 0,
        y: 0,
        z: 0,
        pitch: 0,
        roll: 0,
        yaw: 0,
        timestamp: null,
        source: 'unknown'
      }
      this.actualFlightOrigin = { lat: null, lon: null, alt: null }
    }
  }
})