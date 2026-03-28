/**
 * Pinia Store - 无人机状态管理
 * 单一数据源，管理所有无人机相关状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import backend from '@/api/backend'
import { buildApiUrl, getBackendBaseUrl } from '@/api/backend'

// WebSocket composable
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

export const useDroneStore = defineStore('drone', {
  state: () => ({
    // ========== 连接状态 ==========
    connected: false,
    connecting: false,
    udpConnected: false,
    lastBackendMessage: null,
    
    // ========== ExtY_FCS_T 飞控完整数据结构 ==========
    // PWM输出数据 (ExtY_FCS_OUTPUTPWM_T)
    pwms: [0, 0, 0, 0, 0, 0, 0, 0],  // 8个通道的归一化PWM比值
    
    // 飞控状态 (ExtY_FCS_STATES_T)
    fcsStates: {
      states_lat: 0,          // 纬度
      states_lon: 0,          // 经度
      states_height: 0,        // 高度
      states_Vx_GS: 0,        // 地速X
      states_Vy_GS: 0,        // 地速Y
      states_Vz_GS: 0,        // 地速Z
      states_p: 0,            // 滚转角速度
      states_q: 0,            // 俯仰角速度
      states_r: 0,            // 偏航角速度
      states_phi: 0,          // 滚转角
      states_theta: 0,        // 俯仰角
      states_psi: 0           // 偏航角
    },
    
    // 飞控遥控数据 (ExtY_FCS_DATAFUTABA_T)
    fcsData: {
      Tele_ftb_Roll: 0,             // 遥控滚转
      Tele_ftb_Pitch: 0,            // 遥控俯仰
      Tele_ftb_Yaw: 0,              // 遥控偏航
      Tele_ftb_Col: 0,              // 遥控油门
      Tele_ftb_Switch: 0,           // 遥控开关
      Tele_ftb_com_Ftb_fail: 0      // 遥控通信失败标志
    },
    
    // GN&C总线数据 (ExtY_FCS_GNCBUS_T)
    gncBus: {
      GNCBus_CmdValue_Vx_cmd: 0,   // X速度指令
      GNCBus_CmdValue_Vy_cmd: 0,   // Y速度指令
      GNCBus_CmdValue_height_cmd: 0,  // 高度指令
      GNCBus_CmdValue_psi_cmd: 0,  // 偏航指令
      GNCBus_TokenMode_rud_state: 0,
      GNCBus_TokenMode_ail_state: 0,
      GNCBus_TokenMode_ele_state: 0,
      GNCBus_TokenMode_col_state: 0
    },
    
    // 避障标志 (ExtY_FCS_AVOIFLAG_T)
    avoiFlag: {
      AvoiFlag_LaserRadar_Enabled: false,
      AvoiFlag_AvoidanceFlag: false,
      AvoiFlag_GuideFlag: false
    },
    
    // ========== 系统状态 ==========
    systemStatus: {
      mode: 'DISARMED',  // 飞行模式
      battery: 0,         // 电池百分比
      voltage: 0,         // 电池电压 (V)
      current: 0,         // 电池电流 (A)
      gpsSatellites: 0,    // GPS卫星数
      linkQuality: 0       // 链路质量
    },
    
    // ========== 向后兼容的简化状态 ==========
    // 保持原有的简化数据结构以便兼容旧代码
    attitude: {
      roll: 0,
      pitch: 0,
      yaw: 0
    },
    position: {
      lat: 0,
      lon: 0,
      alt: 0,
      relAlt: 0
    },
    velocity: {
      x: 0,
      y: 0,
      z: 0
    },
    angularVelocity: {
      p: 0,
      q: 0,
      r: 0
    },
    motors: [0, 0, 0, 0, 0, 0],
    
    // ========== 控制循环状态 ==========
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
    
    // ========== ESC数据 (ExtY_FCS_ESC_T) ==========
    escData: {
      esc1_error_count: 0,
      esc2_error_count: 0,
      esc3_error_count: 0,
      esc4_error_count: 0,
      esc5_error_count: 0,
      esc6_error_count: 0,
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
    
    // ========== GCS数据 (ExtY_FCS_DATAGCS_T) ==========
    gcsData: {
      Tele_GCS_CmdIdx: 0,        // 指令索引
      Tele_GCS_Mission: 0,        // 任务编号
      Tele_GCS_Val: 0,            // 指令参数
      Tele_GCS_com_GCS_fail: 0    // GCS通信失败标志
    },
    
    // ========== 飞控参数 ==========
    fcsParam: {
      paramId: 0,
      paramValue: 0,
      paramMin: 0,
      paramMax: 0
    },
    
    // ========== 规划系统遥测 ==========
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
    
    // ========== 航迹数据 ==========
    trajectory: [],     // 实际飞行轨迹点（飞控遥测）[{x, y, z, timestamp}]
    globalPath: [],  // 全局路径点 [{x, y, z}]
    localTraj: [],  // 局部轨迹点 [{x, y, z}]
    
    // ========== 障碍物数据 ==========
    obstacles: [],      // 障碍物列表 (Planning Telemetry)
    
    // ========== 日志数据 ==========
    logs: [],          // 系统日志列表
    
    // ========== 历史数据（用于图表显示）==========
    history: {
      // 姿态角历史数据（添加初始默认值）
      rollTarget: [{ value: 0, timestamp: Date.now() }],
      rollActual: [{ value: 0, timestamp: Date.now() }],
      pitchTarget: [{ value: 0, timestamp: Date.now() }],
      pitchActual: [{ value: 0, timestamp: Date.now() }],
      yawTarget: [{ value: 0, timestamp: Date.now() }],
      yawActual: [{ value: 0, timestamp: Date.now() }],
      // 速度历史数据
      speedTarget: [{ value: 0, timestamp: Date.now() }],
      speedActual: [{ value: 0, timestamp: Date.now() }],
      // 高度历史数据
      altitudeTarget: [{ value: 0, timestamp: Date.now() }],
      altitudeActual: [{ value: 0, timestamp: Date.now() }],
      // 控制输出历史数据
      controlU1: [{ value: 0, timestamp: Date.now() }],
      controlU2: [{ value: 0, timestamp: Date.now() }],
      controlU3: [{ value: 0, timestamp: Date.now() }],
      controlU4: [{ value: 0, timestamp: Date.now() }],
      // 速度分量历史数据
      velocityX: [{ value: 0, timestamp: Date.now() }],
      velocityY: [{ value: 0, timestamp: Date.now() }],
      velocityZ: [{ value: 0, timestamp: Date.now() }],
      // 角速度历史数据
      angularRateP: [{ value: 0, timestamp: Date.now() }],
      angularRateQ: [{ value: 0, timestamp: Date.now() }],
      angularRateR: [{ value: 0, timestamp: Date.now() }],
      // 控制令牌状态
      tokenRud: [{ value: 0, timestamp: Date.now() }],
      tokenAil: [{ value: 0, timestamp: Date.now() }],
      tokenEle: [{ value: 0, timestamp: Date.now() }],
      tokenCol: [{ value: 0, timestamp: Date.now() }],
      // 遥控输入历史
      futabaRoll: [{ value: 0, timestamp: Date.now() }],
      futabaPitch: [{ value: 0, timestamp: Date.now() }],
      futabaYaw: [{ value: 0, timestamp: Date.now() }],
      // PWM历史数据（添加初始默认值）
      pwm1: [{ value: 0, timestamp: Date.now() }],
      pwm2: [{ value: 0, timestamp: Date.now() }],
      pwm3: [{ value: 0, timestamp: Date.now() }],
      pwm4: [{ value: 0, timestamp: Date.now() }],
      pwm5: [{ value: 0, timestamp: Date.now() }],
      pwm6: [{ value: 0, timestamp: Date.now() }],
      pwm7: [{ value: 0, timestamp: Date.now() }],
      pwm8: [{ value: 0, timestamp: Date.now() }]
    },
    
    // ========== KPI历史数据（用于KPI图表显示）==========
    kpiHistory: {
      computing: [],       // 算力资源历史
      communication: [],   // 通信资源历史
      energy: [],         // 能耗指标历史
      mission: [],         // 任务效能历史
      performance: []      // 飞行性能历史
    },

    metricTrends: {
      planningTimeMs: [{ value: 0, timestamp: Date.now() }],
      controlJitterMs: [{ value: 0, timestamp: Date.now() }],
      trackingRmse: [{ value: 0, timestamp: Date.now() }],
      obstacleCount: [{ value: 0, timestamp: Date.now() }],
      pathDeviationM: [{ value: 0, timestamp: Date.now() }],
      pathErrorX: [{ value: 0, timestamp: Date.now() }],
      pathErrorY: [{ value: 0, timestamp: Date.now() }],
      pathErrorZ: [{ value: 0, timestamp: Date.now() }]
    },

    // ========== 新版实时视图状态（来自结构化推送）==========
    realtimeViews: {
      flightState: {
        latitude: 0,
        longitude: 0,
        height: 0,
        vx: 0,
        vy: 0,
        vz: 0,
        p_rate: 0,
        q_rate: 0,
        r_rate: 0,
        phi: 0,
        theta: 0,
        psi: 0,
        raw: {}
      },
      planningState: {
        cmd_idx: 0,
        mission_id: 0,
        mission_value: 0,
        gcs_link_fail: false,
        avoid_enabled: false,
        avoid_triggered: false,
        guide_flag: false,
        next_waypoint: 0,
        next_segment_index: 0,
        ab_next_waypoint: 0,
        planning_status: 0,
        global_path_count: 0,
        local_traj_count: 0,
        obstacle_count: 0,
        current_pos_x: 0,
        current_pos_y: 0,
        current_pos_z: 0
      },
      systemPerformance: {
        perception_latency_ms: 0,
        planning_time_ms: null,
        tracking_rmse: null,
        control_jitter_ms: null,
        planner_cycle_hz: null,
        radar_fps: null,
        attitude_peak_phi_deg: 0,
        obstacle_count: 0,
        avoid_trigger_count: 0,
        mission_switch_count: 0,
        cmd_idx: 0,
        mission_id: 0,
        esc_power_pct: 0,
        esc_power_pct_avg: 0,
        esc_rpm_avg: 0,
        esc_rpm_max: 0,
        esc_power_max: 0,
        downlink_loss_rate: 0,
        trusted: {},
        derived: {},
        metric_quality: {}
      },
      updatedAt: null
    },

    experimentContext: {
      caseId: '',
      planCaseId: '',
      selectedPlanCaseId: '',
      figureRunId: '',
      figureBatchId: '',
      figureBatchGroup: '',
      figureLedgerRange: '',
      experimentType: '',
      chapterTarget: '',
      lawValidationScope: '',
      analysisRunId: '',
      scenarioName: 'Scenario Default',
      scenarioId: 'scenario_default',
      scenarioSource: 'default',
      scenarioConfidence: 0,
      environmentClass: 'unknown',
      obstacleDensity: 'unknown',
      windLevel: 'unknown',
      linkQualityLevel: 'unknown',
      sensorQualityLevel: 'unknown',
      missionPhase: 'idle',
      triggerPolicy: '',
      availableCases: [],
      updatedAt: null,
      caseMeta: {
        repeatIndex: null,
        durationSec: null,
        evaluationWindowSec: null
      },
      task: {
        plannedCmdIdx: 0,
        effectiveCmdIdx: 0,
        missionId: 0,
        taskName: 'Idle',
        taskGroup: 'idle',
        phase: 'idle',
        source: 'default'
      },
      architecture: {
        architectureId: '',
        displayName: 'Baseline Balanced',
        mappingProfile: '',
        adaptationMode: '',
        focus: ''
      },
      architectureProfiles: {
        baselineProfiles: [],
        candidateProfiles: [],
        researchProfiles: []
      },
      disturbanceTags: [],
      heuristicTags: []
    },

    pipelineStatus: {
      rawRecordingStatus: 'waiting',
      standardFilesStatus: 'missing',
      dsmStatus: 'waiting',
      evaluationStatus: 'waiting',
      optimizationStatus: 'waiting',
      archiveStatus: 'waiting',
      figureAssetReady: false,
      figureBatchManifestPath: '',
      standardFiles: {
        fcsTelemetry: 'missing',
        planningTelemetry: 'missing',
        radarData: 'missing',
        busTraffic: 'missing',
        cameraData: 'missing'
      },
      updatedAt: null
    },

    dsmSummary: {
      nodeCount: null,
      edgeCount: null,
      crossModuleInteractions: null,
      totalBusBytes: null,
      avgCrossLatency: null,
      globalStatsReady: false,
      figureRunId: '',
      figureBatchId: '',
      figureBatchGroup: '',
      figureLedgerRange: '',
      experimentType: '',
      chapterTarget: '',
      lawValidationScope: '',
      analysisRunId: '',
      figureAssetReady: false,
      figureBatchManifestPath: '',
      updatedAt: null
    },

    evaluationSummary: {
      baselineAllocationId: '',
      candidateAllocationId: '',
      finalCompositeScore: null,
      constraintViolationCount: null,
      domainScores: {},
      baselineDelta: {},
      evaluationReady: false,
      figureRunId: '',
      figureBatchId: '',
      figureBatchGroup: '',
      figureLedgerRange: '',
      experimentType: '',
      chapterTarget: '',
      lawValidationScope: '',
      analysisRunId: '',
      figureAssetReady: false,
      figureBatchManifestPath: '',
      updatedAt: null
    },

    architectureRecommendation: {
      currentArchitecture: '',
      recommendedArchitecture: '',
      scoreDelta: null,
      crossCountDelta: null,
      powerDelta: null,
      constraintPass: null,
      riskText: '',
      triggerEvidence: [],
      candidates: [],
      figureRunId: '',
      figureBatchId: '',
      figureBatchGroup: '',
      figureLedgerRange: '',
      experimentType: '',
      chapterTarget: '',
      lawValidationScope: '',
      analysisRunId: '',
      figureAssetReady: false,
      figureBatchManifestPath: '',
      updatedAt: null
    },

    figureAssetStatus: {
      figureRunId: '',
      figureBatchId: '',
      figureBatchGroup: '',
      figureLedgerRange: '',
      experimentType: '',
      chapterTarget: '',
      lawValidationScope: '',
      analysisRunId: '',
      figureAssetReady: false,
      figureBatchManifestPath: '',
      updatedAt: null
    },

    captureState: {
      recording: false,
      inputPorts: [],
      flightControlRateHz: 0,
      planningRateHz: 0,
      radarRateHz: 0,
      perceptionRateHz: 0,
      packetCounts: {},
      lastPacketTs: null,
      parseErrorCount: 0,
      lastError: '',
      outputDir: '',
      bytesWritten: 0
    },

    dataQuality: {
      parseErrorCount: 0,
      windowMissingCount: 0,
      planningGapMs: null,
      flightControlGapMs: null,
      radarGapMs: null,
      radarMissing: true,
      healthLevel: 'unknown',
      healthText: 'waiting for stream'
    },

    // ========== 新版KPI汇总（来自kpi_update）==========
    kpiSummary: {
      dimensions: {
        computing: null,
        communication: null,
        energy: null,
        mission: null,
        performance: null
      },
      indicators: {},
      windowMetrics: {},
      overallScore: null,
      updatedAt: null
    },
    
    // ========== 数据记录信息 ==========
    dataRecording: {
      enabled: false,        // 是否启用数据记录
      recordingStartTime: null, // 记录开始时间
      recordCount: 0,        // 记录的数据包数量
      recordFilePath: '',      // 记录文件路径
      lastRecordTime: null,     // 最后记录时间
      sessionId: '',
      totalBytes: 0,
      functionStats: []
    },
    
    // ========== 系统模式 ==========
    systemMode: 'REALTIME',  // 系统模式: 'REALTIME' (实时模式) 或 'REPLAY' (回放模式)
    
    // ========== 回放状态 ==========
    replayStatus: {
      is_loaded: false,      // 是否已加载回放文件
      is_playing: false,      // 是否正在播放
      replay_active: false,   // 回放是否激活
      current_file: null,     // 当前回放文件路径
      current_idx: 0,        // 当前索引
      total_rows: 0,        // 总行数
      total_time: 0,         // 总时长（秒）
      speed: 1.0,           // 播放速度
      progress: 0,           // 进度百分比
      current_time: 0        // 当前时间（秒）
    },
    
    // ========== 回放分析数据 ==========
    // 用于变量选择和分析面板的数据
    replayAnalysis: {
      categorizedVars: {},    // 分类变量
      selectedVariables: [],  // 已选变量
      loading: false,        // 加载状态
      error: null,           // 错误信息
      timeAxis: [],          // 时间轴数据
      seriesData: {},        // 系列数据
      allVariables: [],      // 所有变量
      hasData: false         // 是否有数据
    },
    
    // ========== 配置数据 ==========
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
    // 连接状态
    isConnected: (state) => state.connected,
    isUdpConnected: (state) => state.udpConnected,
    canSendCommands: (state) => state.connected && state.udpConnected,
    isConnectedText: (state) => state.connected ? '已连接' : '未连接',
    
    // 是否已解算
    isArmed: (state) => state.systemStatus.mode !== 'DISARMED',
    
    // 获取当前模式显示文本
    modeText: (state) => {
      const modeMap = {
        'DISARMED': '未解算',
        'MANUAL': '手动',
        'AUTO': '自动',
        'GUIDED': '引导',
        'RTL': '返航'
      }
      return modeMap[state.systemStatus.mode] || state.systemStatus.mode
    },
    
    // 电池电压告警
    lowBattery: (state) => state.systemStatus.voltage < 21.0,
    
    // 链路质量指示
    linkQualityText: (state) => {
      if (state.systemStatus.linkQuality > 80) return '优良'
      if (state.systemStatus.linkQuality > 50) return '良好'
      if (state.systemStatus.linkQuality > 30) return '一般'
      return '差'
    }
  },
  
  actions: {
    _safeNumber(value, fallback = 0) {
      const parsed = Number(value)
      return Number.isFinite(parsed) ? parsed : fallback
    },

    _looksLikeRadians(value) {
      return Math.abs(value) <= (2 * Math.PI + 0.5)
    },

    _normalizeAngleToRadians(value) {
      const numericValue = this._safeNumber(value)
      if (this._looksLikeRadians(numericValue)) {
        return numericValue
      }
      return numericValue * Math.PI / 180
    },

    _normalizeAngleToDegrees(value) {
      const numericValue = this._safeNumber(value)
      if (this._looksLikeRadians(numericValue)) {
        return numericValue * 180 / Math.PI
      }
      return numericValue
    },

    _degreesToRadians(value) {
      return this._safeNumber(value) * Math.PI / 180
    },

    _buildCaseId(sessionId = '') {
      const dateMatch = String(sessionId || '').match(/(\d{8})/)
      const dateToken = dateMatch?.[1] || new Date().toISOString().slice(0, 10).replace(/-/g, '')
      return `case001_${dateToken}`
    },

    _pickDefinedValue(...values) {
      for (const value of values) {
        if (value !== undefined && value !== null && value !== '') {
          return value
        }
      }
      return undefined
    },

    _extractFigureSemantics(...sources) {
      const mappings = [
        ['figure_run_id', 'figureRunId'],
        ['figure_batch_id', 'figureBatchId'],
        ['figure_batch_group', 'figureBatchGroup'],
        ['figure_ledger_range', 'figureLedgerRange'],
        ['experiment_type', 'experimentType'],
        ['chapter_target', 'chapterTarget'],
        ['law_validation_scope', 'lawValidationScope'],
        ['analysis_run_id', 'analysisRunId'],
        ['figure_asset_ready', 'figureAssetReady'],
        ['figure_batch_manifest_path', 'figureBatchManifestPath']
      ]
      const figureContext = {}

      mappings.forEach(([snakeKey, camelKey]) => {
        const candidates = []
        sources.forEach((source) => {
          if (!source || typeof source !== 'object') {
            return
          }
          candidates.push(source[snakeKey], source[camelKey])
        })
        const value = this._pickDefinedValue(...candidates)
        if (value !== undefined) {
          figureContext[camelKey] = value
        }
      })

      return figureContext
    },

    _buildFigurePatch(figureContext = {}) {
      const patch = {}
      const fields = [
        'figureRunId',
        'figureBatchId',
        'figureBatchGroup',
        'figureLedgerRange',
        'experimentType',
        'chapterTarget',
        'lawValidationScope',
        'analysisRunId',
        'figureAssetReady',
        'figureBatchManifestPath'
      ]

      fields.forEach((field) => {
        if (figureContext[field] !== undefined) {
          patch[field] = figureContext[field]
        }
      })

      return patch
    },

    _applyFigureContext(figureContext = {}) {
      const figurePatch = this._buildFigurePatch(figureContext)
      const contextFields = [
        'figureRunId',
        'figureBatchId',
        'figureBatchGroup',
        'figureLedgerRange',
        'experimentType',
        'chapterTarget',
        'lawValidationScope',
        'analysisRunId'
      ]
      const nextContext = { ...this.experimentContext }
      let changed = false

      contextFields.forEach((field) => {
        if (figurePatch[field] !== undefined && nextContext[field] !== figurePatch[field]) {
          nextContext[field] = figurePatch[field]
          changed = true
        }
      })

      if (changed) {
        nextContext.updatedAt = Date.now()
        this.experimentContext = nextContext
      }

      return figurePatch
    },

    _buildMissionPhase(missionId = 0) {
      const phaseMap = {
        0: 'idle',
        1: 'manual',
        2: 'standby',
        3: 'guided',
        4: 'takeoff',
        5: 'cruise',
        6: 'descent',
        14: 'auto_takeoff',
        15: 'auto_landing',
        16: 'hover',
        24: 'avoidance_enabled',
        25: 'avoidance_disabled'
      }
      const normalizedMissionId = this._safeNumber(missionId, 0)
      return phaseMap[normalizedMissionId] || `mission_${normalizedMissionId}`
    },

    _pushBoundedHistory(targetKey, payload, maxPoints = 120) {
      if (!this.kpiHistory[targetKey] || !payload) {
        return
      }

      this.kpiHistory[targetKey].push(payload)
      if (this.kpiHistory[targetKey].length > maxPoints) {
        this.kpiHistory[targetKey] = this.kpiHistory[targetKey].slice(-maxPoints)
      }
    },

    _pushMetricTrend(targetKey, value, timestamp = Date.now(), maxPoints = 120) {
      if (!this.metricTrends[targetKey]) {
        return
      }

      if (value === null || value === undefined || value === '') {
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

    _extractPathPoint(point = {}) {
      return {
        x: this._safeNumber(point.x ?? point.pos_x ?? point.current_pos_x ?? point[0]),
        y: this._safeNumber(point.y ?? point.pos_y ?? point.current_pos_y ?? point[1]),
        z: this._safeNumber(point.z ?? point.pos_z ?? point.current_pos_z ?? point[2])
      }
    },

    _computeMinPathDistance(referencePoint, path = []) {
      if (!referencePoint || !Array.isArray(path) || !path.length) {
        return null
      }

      let minDistance = Number.POSITIVE_INFINITY
      path.forEach((item) => {
        const candidate = this._extractPathPoint(item)
        const distance = Math.sqrt(
          Math.pow(referencePoint.x - candidate.x, 2) +
          Math.pow(referencePoint.y - candidate.y, 2) +
          Math.pow(referencePoint.z - candidate.z, 2)
        )
        if (distance < minDistance) {
          minDistance = distance
        }
      })

      return Number.isFinite(minDistance) ? minDistance : null
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
          Math.pow(referencePoint.x - candidate.x, 2) +
          Math.pow(referencePoint.y - candidate.y, 2) +
          Math.pow(referencePoint.z - candidate.z, 2)
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
        this.actualFlightOrigin = {
          lat: latitude,
          lon: longitude,
          alt: altitude
        }
      }

      const originLat = Number(this.actualFlightOrigin.lat)
      const originLon = Number(this.actualFlightOrigin.lon)
      const originAlt = this._safeNumber(this.actualFlightOrigin.alt, 0)
      const latScale = 111320
      const lonScale = 111320 * Math.cos((originLat * Math.PI) / 180)

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
      this.addTrajectoryPoint(pose.x, pose.y, pose.z, timestamp)
      return pose
    },

    _updatePathDeviationTrend(timestamp = Date.now()) {
      const referencePoint = this._getActualFlightReferencePoint()

      if (!referencePoint) {
        return
      }

      const nearestLocalPoint = this._findNearestPathPoint(referencePoint, this.localTraj)
      const nearestGlobalPoint = this._findNearestPathPoint(referencePoint, this.globalPath)
      const targetPoint = nearestLocalPoint || nearestGlobalPoint

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

    async sendRemoteCommand(cmdId, cmdName) {
      if (!this.connected) {
        this.addLog('未连接到后端，无法发送指令', 'warning')
        return null
      }

      if (!this.udpConnected) {
        this.addLog('UDP未连接，指令不会发往机载端', 'warning')
        return null
      }

      this.gcsData.Tele_GCS_CmdIdx = cmdId

      return await this.sendCommandREST('cmd_idx', {
        cmdId,
        name: cmdName
      })
    },

    /**
     * 初始化 WebSocket 连接
     * 注意：此方法应在组件的 setup() 中调用，不能在 action 中使用生命周期钩子
     */
    initWebSocket() {
      console.log('[Store] 初始化WebSocket连接...')
      
      if (wsInstance) {
        console.warn('WebSocket 已存在，先断开')
        this.disconnect()
      }
      
      wsInstance = useWebSocket(getWebSocketUrl())
      
      // 注册回调函数（使用on方法，避免覆盖）
      wsInstance.onOpen(() => {
        console.log('[Store] WebSocket 连接已建立')
        this.connected = true
        this.connecting = false
        this.addLog('WebSocket 连接已建立', 'info')
      })
      
      wsInstance.onClose((event) => {
        console.log('[Store] WebSocket 连接已断开')
        this.connected = false
        this.connecting = false
        this.addLog('WebSocket 连接已断开', 'warning')
      })
      
      wsInstance.onError((error) => {
        console.error('[Store] WebSocket 错误:', error)
        this.connecting = false
        const errorText = error?.message || error?.type || '连接异常'
        this.addLog(`WebSocket 错误: ${errorText}`, 'error')
      })
      
      wsInstance.onMessage((message) => {
        // console.log('[Store] WebSocket收到消息')
        this.handleMessage(message)
      })
      
      wsInstance.connect()
    },
    
    /**
     * 断开 WebSocket 连接
     * 注意：此方法应在组件的 onUnmounted 生命周期钩子中调用
     */
    disconnect() {
      if (wsInstance) {
        wsInstance.disconnect()
        wsInstance = null
      }
      this.connected = false
      this.connecting = false
    },
    
    /**
     * 连接（UDP)
     */
    async connect() {
      if (this.connected || this.connecting) {
        console.warn('已连接或正在连接中')
        return
      }
      
      this.connecting = true
      
      try {
        // 初始化 WebSocket
        this.initWebSocket()
      } catch (error) {
        console.error('连接失败:', error)
        this.addLog(`连接失败: ${error.message}`, 'error')
        this.connecting = false
      }
    },
    
    /**
     * 处理接收到的消息
     */
    handleMessage(message) {
      try {
        const data = typeof message === 'string' ? JSON.parse(message) : message
        this.lastBackendMessage = data
        
        // Console log removed for performance
        // console.log('[Store] 收到WebSocket消息:', data.type, data)
        
        // 处理UDP数据包装类型
        if (data.type === 'udp_data') {
          const innerType = data.data?.type || 'unknown'
          const innerData = data.data?.data || data.data || {}
          
          // console.log('[Store] 解析UDP数据，内部类型:', innerType, '内部数据:', innerData)
          
          switch (innerType) {
            case 'fcs_states':
              this.updateFlightState(innerData)
              // this.addLog('收到飞行状态数据', 'info')
              break
            
            case 'fcs_pwms':
              this.updateMotorPWMs(innerData)
              this.addHistoryData('pwmData', innerData)
              // this.addLog(`收到PWM数据 [${Array.isArray(innerData) ? innerData.length : (innerData.pwms?.length || 0)}个通道]`, 'info')
              break
            
            case 'fcs_datactrl':
              this.updateControlLoop(innerData)
              // this.addLog('收到控制循环数据', 'info')
              break
            
            case 'fcs_gncbus':
              this.updateGNCBus(innerData)
              // this.addLog('收到GN&C总线数据', 'info')
              break
            
            case 'avoiflag':
              this.updateAvoiFlag(innerData)
              // this.addLog('收到避障标志', 'info')
              break
              
            case 'fcs_datafutaba':
              this.updateFCSData(innerData)
              // this.addLog('收到遥控数据', 'info')
              break
            
            case 'fcs_esc':
              this.updateESCData(innerData)
              // this.addLog('收到电机数据', 'info')
              break
            
            case 'fcs_datagcs':
              this.updateGCSData(innerData)
              this.addLog('收到GCS数据', 'info')
              break
            
            case 'fcs_param':
              this.updateFCSParam(innerData)
              // this.addLog('收到参数数据', 'info')
              break

            case 'lidar_obstacles':
              this.updateLidarObstacles(innerData)
              break

            case 'lidar_status':
              this.updateLidarStatus(innerData)
              break
              
            case 'planning_telemetry':
              this.updatePlanningTelemetry(innerData)
              break
            
            default:
              console.warn('[Store] 未知UDP数据类型:', innerType)
          }
          return
        }
        
        switch (data.type) {
          case 'kpi_update':
            this.applyKPIUpdate(data)
            break

          case 'flight_state_update':
            this.applyFlightStateUpdate(data.data)
            break

          case 'planning_state_update':
            this.applyPlanningStateUpdate(data.data)
            break

          case 'system_performance_update':
            this.applySystemPerformanceUpdate(data.data)
            break

          case 'capture_overview_update':
            this.applyCaptureOverviewUpdate(data)
            break

          case 'data_quality_update':
            this.applyDataQualityUpdate(data)
            break

          case 'fcs_states':
            this.updateFlightState(data.data)
            break
          
          case 'fcs_pwms':
            this.updateMotorPWMs(data.data)
            this.addHistoryData('pwmData', data.data)
            break
          
          case 'fcs_datactrl':
            this.updateControlLoop(data.data)
            break
          
          case 'fcs_gncbus':
            this.updateGNCBus(data.data)
            break
          
          case 'avoiflag':
            this.updateAvoiFlag(data.data)
            break
          
          case 'fcs_datafutaba':
            this.updateFCSData(data.data)
            break
          
          case 'fcs_esc':
            this.updateESCData(data.data)
            break
          
          case 'fcs_datagcs':
            this.updateGCSData(data.data)
            break
          
          case 'fcs_param':
            this.updateFCSParam(data.data)
            break

          case 'lidar_status':
            this.updateLidarStatus(data.data)
            break
          
          case 'planning_telemetry':
            this.updatePlanningTelemetry(data.data)
            break
          
          case 'obstacles':
            this.updateObstacles(data.data)
            break
          
          case 'system_status':
            this.updateSystemStatus(data.data)
            break
          
          case 'log':
            this.addLog(data.message, data.level)
            break
          
          case 'command_response':
            this.handleCommandResponse(data)
            break

          case 'recording_status':
            this.applyRecordingStatus(data)
            break

          case 'experiment_context_update':
            this.applyExperimentContextUpdate(data)
            break

          case 'pipeline_status_update':
            this.applyPipelineStatusUpdate(data)
            break

          case 'dsm_summary_update':
            this.applyDsmSummaryUpdate(data)
            break

          case 'evaluation_summary_update':
            this.applyEvaluationSummaryUpdate(data)
            break

          case 'architecture_recommendation_update':
            this.applyArchitectureRecommendationUpdate(data)
            break

          case 'figure_asset_status_update':
            this.applyFigureAssetStatusUpdate(data)
            break

          case 'recording_response':
            if (data.session_info || data.session_id !== undefined) {
              this.applyRecordingStatus({
                is_active: data.status === 'success' ? data.message !== '录制已停止' : this.dataRecording.enabled,
                session_id: data.session_id,
                session_info: data.session_info
              })
            }
            break

          case 'udp_status_change':
            this.udpConnected = data.status === 'connected'
            this.addLog(
              `UDP链路${this.udpConnected ? '已连接' : '已断开'}`,
              this.udpConnected ? 'success' : 'warning'
            )
            break
          
          case 'config_update':
            if (data.config_type === 'connection' && data.data) {
              this.updateConfig(data.data)
            }
            break
          
          case 'system_mode_change':
            this.updateSystemMode(data.mode)
            break
          
          case 'replay_status':
            this.updateReplayStatus(data.data)
            // 同步回放进度到本地的 replayStatus
            break
          
          case 'replay_response':
            // 处理回放控制响应
            if (data.action === 'play') {
              this.replayStatus.is_playing = true
            } else if (data.action === 'pause') {
              this.replayStatus.is_playing = false
            } else if (data.action === 'load') {
              this.replayStatus.total_time = data.total_time || 0
            }
            break
          
          default:
            console.debug('未知消息类型:', data.type, data)
        }
      } catch (error) {
        console.error('处理消息失败:', error)
      }
    },
    
    /**
     * 更新飞行状态 - 兼容新旧数据格式
     */
    updateFlightState(data) {
      // console.log('[Store] 更新飞行状态:', data)
      
      // 方式1: 新格式 - 直接更新fcsStates完整结构体，并同步到通用状态变量
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
        const phiRad = this._degreesToRadians(phiDeg)
        this.fcsStates.states_phi = phiRad
        this.attitude.roll = phiDeg
      }
      if (data.states_theta !== undefined) {
        const thetaDeg = this._safeNumber(data.states_theta)
        const thetaRad = this._degreesToRadians(thetaDeg)
        this.fcsStates.states_theta = thetaRad
        this.attitude.pitch = thetaDeg
      }
      if (data.states_psi !== undefined) {
        const psiDeg = this._safeNumber(data.states_psi)
        const psiRad = this._degreesToRadians(psiDeg)
        this.fcsStates.states_psi = psiRad
        this.attitude.yaw = psiDeg
      }
      
      // 方式2: 旧格式 - 保持向后兼容
      if (data.roll !== undefined) {
        const rollDeg = this._safeNumber(data.roll)
        this.attitude.roll = rollDeg
        this.fcsStates.states_phi = this._degreesToRadians(rollDeg)
      }
      if (data.pitch !== undefined) {
        const pitchDeg = this._safeNumber(data.pitch)
        this.attitude.pitch = pitchDeg
        this.fcsStates.states_theta = this._degreesToRadians(pitchDeg)
      }
      if (data.yaw !== undefined) {
        const yawDeg = this._safeNumber(data.yaw)
        this.attitude.yaw = yawDeg
        this.fcsStates.states_psi = this._degreesToRadians(yawDeg)
      }
      
      if (data.latitude !== undefined) {
        this.position.lat = parseFloat(data.latitude)
        this.fcsStates.states_lat = parseFloat(data.latitude)
      }
      if (data.longitude !== undefined) {
        this.position.lon = parseFloat(data.longitude)
        this.fcsStates.states_lon = parseFloat(data.longitude)
      }
      if (data.altitude !== undefined) {
        const alt = parseFloat(data.altitude)
        this.position.alt = alt
        this.position.relAlt = alt
        this.fcsStates.states_height = alt
      }
      
      if (data.velocity_x !== undefined) {
        this.velocity.x = parseFloat(data.velocity_x)
        this.fcsStates.states_Vx_GS = parseFloat(data.velocity_x)
      }
      if (data.velocity_y !== undefined) {
        this.velocity.y = parseFloat(data.velocity_y)
        this.fcsStates.states_Vy_GS = parseFloat(data.velocity_y)
      }
      if (data.velocity_z !== undefined) {
        this.velocity.z = parseFloat(data.velocity_z)
        this.fcsStates.states_Vz_GS = parseFloat(data.velocity_z)
      }
      
      if (data.angular_velocity_x !== undefined) {
        const p = this._safeNumber(data.angular_velocity_x)
        this.angularVelocity.p = p
        this.fcsStates.states_p = p
      }
      if (data.angular_velocity_y !== undefined) {
        const q = this._safeNumber(data.angular_velocity_y)
        this.angularVelocity.q = q
        this.fcsStates.states_q = q
      }
      if (data.angular_velocity_z !== undefined) {
        const r = this._safeNumber(data.angular_velocity_z)
        this.angularVelocity.r = r
        this.fcsStates.states_r = r
      }
      
      // 记录历史数据用于图表显示
      this.addHistoryData('flightState', data)

      this._updateActualPoseFromTelemetry(Date.now())
    },
    
    /**
     * 更新电机PWM数据 - 兼容新旧格式
     */
    updateMotorPWMs(data) {
      let pwmArray = null
      
      // 方式1: 新格式 - pwms数组
      if (Array.isArray(data)) {
        pwmArray = data
      }
      // 方式2: 新格式 - 对象包含pwms字段
      else if (Array.isArray(data?.pwms)) {
        pwmArray = data.pwms
      }
      
      if (pwmArray && pwmArray.length > 0) {
        // 更新完整的pwms数组（支持8通道）
        this.pwms = pwmArray.map(p => parseFloat(p))
        // 保持向后兼容的motors数组（6旋翼）
        this.motors = pwmArray.slice(0, 6).map(p => parseFloat(p))
      }
    },
    
    /**
     * 更新控制循环状态
     */
    updateControlLoop(data) {
      // 更新参考值
      if (data.ref_p !== undefined) this.controlLoop.refRoll = parseFloat(data.ref_p)
      if (data.ref_theta !== undefined) this.controlLoop.refPitch = parseFloat(data.ref_theta)
      if (data.ref_psi !== undefined) this.controlLoop.refYaw = parseFloat(data.ref_psi)
      if (data.ref_h !== undefined) this.controlLoop.refAlt = parseFloat(data.ref_h)
      if (data.ref_vx !== undefined) this.controlLoop.refVx = parseFloat(data.ref_vx)
      if (data.ref_vy !== undefined) this.controlLoop.refVy = parseFloat(data.ref_vy)
      if (data.ref_vz !== undefined) this.controlLoop.refVz = parseFloat(data.ref_vz)
      
      // 更新观测值
      if (data.est_p !== undefined) this.controlLoop.estRoll = parseFloat(data.est_p)
      if (data.est_theta !== undefined) this.controlLoop.estPitch = parseFloat(data.est_theta)
      if (data.est_psi !== undefined) this.controlLoop.estYaw = parseFloat(data.est_psi)
      if (data.est_h !== undefined) this.controlLoop.estAlt = parseFloat(data.est_h)
      if (data.est_vx !== undefined) this.controlLoop.estVx = parseFloat(data.est_vx)
      if (data.est_vy !== undefined) this.controlLoop.estVy = parseFloat(data.est_vy)
      if (data.est_vz !== undefined) this.controlLoop.estVz = parseFloat(data.est_vz)
      
      // 更新控制输出
      if (data.ctrl_u1 !== undefined) this.controlLoop.ctrlU1 = parseFloat(data.ctrl_u1)
      if (data.ctrl_u2 !== undefined) this.controlLoop.ctrlU2 = parseFloat(data.ctrl_u2)
      if (data.ctrl_u3 !== undefined) this.controlLoop.ctrlU3 = parseFloat(data.ctrl_u3)
      if (data.ctrl_u4 !== undefined) this.controlLoop.ctrlU4 = parseFloat(data.ctrl_u4)
      
      // 更新历史数据（用于图表显示）
      this.addHistoryData('controlLoop', data)
    },
    
    /**
     * 更新GN&C总线状态 - 兼容新旧格式
     */
    updateGNCBus(data) {
      // 新格式 - 更新GNC指令值
      if (data.GNCBus_CmdValue_Vx_cmd !== undefined) {
        this.gncBus.GNCBus_CmdValue_Vx_cmd = parseFloat(data.GNCBus_CmdValue_Vx_cmd)
      }
      if (data.GNCBus_CmdValue_Vy_cmd !== undefined) {
        this.gncBus.GNCBus_CmdValue_Vy_cmd = parseFloat(data.GNCBus_CmdValue_Vy_cmd)
      }
      if (data.GNCBus_CmdValue_height_cmd !== undefined) {
        this.gncBus.GNCBus_CmdValue_height_cmd = parseFloat(data.GNCBus_CmdValue_height_cmd)
      }
      if (data.GNCBus_CmdValue_psi_cmd !== undefined) {
        this.gncBus.GNCBus_CmdValue_psi_cmd = parseFloat(data.GNCBus_CmdValue_psi_cmd)
      }
      if (data.GNCBus_TokenMode_rud_state !== undefined) this.gncBus.GNCBus_TokenMode_rud_state = parseInt(data.GNCBus_TokenMode_rud_state)
      if (data.GNCBus_TokenMode_ail_state !== undefined) this.gncBus.GNCBus_TokenMode_ail_state = parseInt(data.GNCBus_TokenMode_ail_state)
      if (data.GNCBus_TokenMode_ele_state !== undefined) this.gncBus.GNCBus_TokenMode_ele_state = parseInt(data.GNCBus_TokenMode_ele_state)
      if (data.GNCBus_TokenMode_col_state !== undefined) this.gncBus.GNCBus_TokenMode_col_state = parseInt(data.GNCBus_TokenMode_col_state)
      
      const actualPoint = this._updateActualPoseFromTelemetry(Date.now()) || this._getActualFlightReferencePoint()
      if (actualPoint) {
        this._updatePathDeviationTrend(Date.now())
      }

      this.addHistoryData('gncBus', data)
    },
    
    /**
     * 更新避障标志 - 兼容新旧格式
     */
    updateAvoiFlag(data) {
      // 新格式 - 直接更新avoiFlag对象
      if (data.AvoiFlag_LaserRadar_Enabled !== undefined) {
        this.avoiFlag.AvoiFlag_LaserRadar_Enabled = !!data.AvoiFlag_LaserRadar_Enabled
      }
      if (data.AvoiFlag_AvoidanceFlag !== undefined) {
        this.avoiFlag.AvoiFlag_AvoidanceFlag = !!data.AvoiFlag_AvoidanceFlag
      }
      if (data.AvoiFlag_GuideFlag !== undefined) {
        this.avoiFlag.AvoiFlag_GuideFlag = !!data.AvoiFlag_GuideFlag
      }
      
      // 旧格式 - 保持向后兼容
      if (data.laser_radar_enabled !== undefined) {
        this.avoiFlag.AvoiFlag_LaserRadar_Enabled = !!data.laser_radar_enabled
        this.systemStatus.laserRadarEnabled = !!data.laser_radar_enabled
      }
      if (data.avoidance_flag !== undefined) {
        this.avoiFlag.AvoiFlag_AvoidanceFlag = !!data.avoidance_flag
        this.systemStatus.avoidanceFlag = !!data.avoidance_flag
      }
      if (data.guide_flag !== undefined) {
        this.avoiFlag.AvoiFlag_GuideFlag = !!data.guide_flag
        this.systemStatus.guideFlag = !!data.guide_flag
      }
      
      // 记录数据
      if (this.dataRecording.enabled) {
        this.recordData('avoiflag', data)
      }
    },
    
    /**
     * 更新飞控遥控数据 (ExtY_FCS_DATAFUTABA_T)
     */
    updateFCSData(data) {
      if (data.Tele_ftb_Roll !== undefined) {
        this.fcsData.Tele_ftb_Roll = parseFloat(data.Tele_ftb_Roll)
      }
      if (data.Tele_ftb_Pitch !== undefined) {
        this.fcsData.Tele_ftb_Pitch = parseFloat(data.Tele_ftb_Pitch)
      }
      if (data.Tele_ftb_Yaw !== undefined) {
        this.fcsData.Tele_ftb_Yaw = parseFloat(data.Tele_ftb_Yaw)
      }
      if (data.Tele_ftb_Col !== undefined) {
        this.fcsData.Tele_ftb_Col = parseFloat(data.Tele_ftb_Col)
      }
      if (data.Tele_ftb_Switch !== undefined) {
        this.fcsData.Tele_ftb_Switch = parseInt(data.Tele_ftb_Switch)
      }
      if (data.Tele_ftb_com_Ftb_fail !== undefined) {
        this.fcsData.Tele_ftb_com_Ftb_fail = parseInt(data.Tele_ftb_com_Ftb_fail)
      }

      this.addHistoryData('fcsData', data)
    },
    
    /**
     * 更新ESC数据 (ExtY_FCS_ESC_T)
     */
    updateESCData(data) {
      // 新格式 - 直接更新完整结构体
      if (data.esc1_error_count !== undefined) {
        this.escData.esc1_error_count = parseInt(data.esc1_error_count)
      }
      if (data.esc2_error_count !== undefined) {
        this.escData.esc2_error_count = parseInt(data.esc2_error_count)
      }
      if (data.esc3_error_count !== undefined) {
        this.escData.esc3_error_count = parseInt(data.esc3_error_count)
      }
      if (data.esc4_error_count !== undefined) {
        this.escData.esc4_error_count = parseInt(data.esc4_error_count)
      }
      if (data.esc5_error_count !== undefined) {
        this.escData.esc5_error_count = parseInt(data.esc5_error_count)
      }
      if (data.esc6_error_count !== undefined) {
        this.escData.esc6_error_count = parseInt(data.esc6_error_count)
      }
      
      if (data.esc1_rpm !== undefined) {
        this.escData.esc1_rpm = parseInt(data.esc1_rpm)
      }
      if (data.esc2_rpm !== undefined) {
        this.escData.esc2_rpm = parseInt(data.esc2_rpm)
      }
      if (data.esc3_rpm !== undefined) {
        this.escData.esc3_rpm = parseInt(data.esc3_rpm)
      }
      if (data.esc4_rpm !== undefined) {
        this.escData.esc4_rpm = parseInt(data.esc4_rpm)
      }
      if (data.esc5_rpm !== undefined) {
        this.escData.esc5_rpm = parseInt(data.esc5_rpm)
      }
      if (data.esc6_rpm !== undefined) {
        this.escData.esc6_rpm = parseInt(data.esc6_rpm)
      }
      
      if (data.esc1_power_rating_pct !== undefined) {
        this.escData.esc1_power_rating_pct = parseInt(data.esc1_power_rating_pct)
      }
      if (data.esc2_power_rating_pct !== undefined) {
        this.escData.esc2_power_rating_pct = parseInt(data.esc2_power_rating_pct)
      }
      if (data.esc3_power_rating_pct !== undefined) {
        this.escData.esc3_power_rating_pct = parseInt(data.esc3_power_rating_pct)
      }
      if (data.esc4_power_rating_pct !== undefined) {
        this.escData.esc4_power_rating_pct = parseInt(data.esc4_power_rating_pct)
      }
      if (data.esc5_power_rating_pct !== undefined) {
        this.escData.esc5_power_rating_pct = parseInt(data.esc5_power_rating_pct)
      }
      if (data.esc6_power_rating_pct !== undefined) {
        this.escData.esc6_power_rating_pct = parseInt(data.esc6_power_rating_pct)
      }
      
      // 旧格式 - 保持向后兼容
      if (Array.isArray(data.error_counts)) {
        this.escData.esc1_error_count = data.error_counts[0] || 0
        this.escData.esc2_error_count = data.error_counts[1] || 0
        this.escData.esc3_error_count = data.error_counts[2] || 0
        this.escData.esc4_error_count = data.error_counts[3] || 0
        this.escData.esc5_error_count = data.error_counts[4] || 0
        this.escData.esc6_error_count = data.error_counts[5] || 0
      }
      if (Array.isArray(data.rpms)) {
        this.escData.esc1_rpm = data.rpms[0] || 0
        this.escData.esc2_rpm = data.rpms[1] || 0
        this.escData.esc3_rpm = data.rpms[2] || 0
        this.escData.esc4_rpm = data.rpms[3] || 0
        this.escData.esc5_rpm = data.rpms[4] || 0
        this.escData.esc6_rpm = data.rpms[5] || 0
      }
      if (Array.isArray(data.power_ratings)) {
        this.escData.esc1_power_rating_pct = data.power_ratings[0] || 0
        this.escData.esc2_power_rating_pct = data.power_ratings[1] || 0
        this.escData.esc3_power_rating_pct = data.power_ratings[2] || 0
        this.escData.esc4_power_rating_pct = data.power_ratings[3] || 0
        this.escData.esc5_power_rating_pct = data.power_ratings[4] || 0
        this.escData.esc6_power_rating_pct = data.power_ratings[5] || 0
      }
    },
    
    /**
     * 更新GCS数据 (ExtY_FCS_DATAGCS_T)
     */
    updateGCSData(data) {
      if (data.Tele_GCS_CmdIdx !== undefined) {
        this.gcsData.Tele_GCS_CmdIdx = parseInt(data.Tele_GCS_CmdIdx)
      } else if (data.CmdIdx !== undefined) {
        this.gcsData.Tele_GCS_CmdIdx = parseInt(data.CmdIdx)
      }

      if (data.Tele_GCS_Mission !== undefined) {
        this.gcsData.Tele_GCS_Mission = parseInt(data.Tele_GCS_Mission)
      } else if (data.Mission !== undefined) {
        this.gcsData.Tele_GCS_Mission = parseInt(data.Mission)
      }

      if (data.Tele_GCS_Val !== undefined) {
        this.gcsData.Tele_GCS_Val = parseFloat(data.Tele_GCS_Val)
      } else if (data.Val !== undefined) {
        this.gcsData.Tele_GCS_Val = parseFloat(data.Val)
      }

      if (data.Tele_GCS_com_GCS_fail !== undefined) {
        this.gcsData.Tele_GCS_com_GCS_fail = parseInt(data.Tele_GCS_com_GCS_fail)
      } else if (data.fail !== undefined) {
        this.gcsData.Tele_GCS_com_GCS_fail = data.fail ? 1 : 0
      }
    },
    
    /**
     * 更新飞控参数
     */
    updateFCSParam(data) {
      if (data.param_id !== undefined) this.fcsParam.paramId = parseInt(data.param_id)
      if (data.param_value !== undefined) this.fcsParam.paramValue = parseFloat(data.param_value)
      if (data.param_min !== undefined) this.fcsParam.paramMin = parseFloat(data.param_min)
      if (data.param_max !== undefined) this.fcsParam.paramMax = parseFloat(data.param_max)
    },
    
    /**
     * 更新规划系统遥测
     */
    updatePlanningTelemetry(data) {
      const position = data.position || {}
      const velocity = data.velocity
      const currentPosX = data.current_pos_x ?? position.x
      const currentPosY = data.current_pos_y ?? position.y
      const currentPosZ = data.current_pos_z ?? position.z
      const currentVel = data.current_vel ?? velocity

      if (data.seq_id !== undefined) this.planningTelemetry.seqId = parseInt(data.seq_id)
      if (data.timestamp !== undefined) this.planningTelemetry.timestamp = parseInt(data.timestamp)
      if (currentPosX !== undefined) this.planningTelemetry.currentPosX = parseFloat(currentPosX)
      if (currentPosY !== undefined) this.planningTelemetry.currentPosY = parseFloat(currentPosY)
      if (currentPosZ !== undefined) this.planningTelemetry.currentPosZ = parseFloat(currentPosZ)
      if (currentVel !== undefined) this.planningTelemetry.currentVel = parseFloat(currentVel)
      if (data.update_flags !== undefined) this.planningTelemetry.updateFlags = parseInt(data.update_flags)
      if (data.status !== undefined) this.planningTelemetry.status = parseInt(data.status)
      if (data.global_path_count !== undefined) this.planningTelemetry.globalPathCount = parseInt(data.global_path_count)
      if (data.local_traj_count !== undefined) this.planningTelemetry.localTrajCount = parseInt(data.local_traj_count)
      if (data.obstacle_count !== undefined) this.planningTelemetry.obstacleCount = parseInt(data.obstacle_count)
      
      // 更新轨迹数组（用于3D可视化）
      if (data.global_path && Array.isArray(data.global_path)) {
        this.globalPath = data.global_path
        console.log('[Store] 更新全局路径:', this.globalPath.length, '个点')
      }
      const localTraj = Array.isArray(data.local_traj) ? data.local_traj : (Array.isArray(data.local_path) ? data.local_path : null)
      if (localTraj) {
        this.localTraj = localTraj
        console.log('[Store] 更新局部轨迹:', this.localTraj.length, '个点')
      }
      if (Array.isArray(data.obstacles)) {
        this.obstacles = data.obstacles
      }

      this._updatePathDeviationTrend(Date.now())
    },
    
    /**
     * 更新障碍物数据
     */
    updateObstacles(data) {
      this.obstacles = data.obstacles || []
    },

    /**
     * 更新系统状态
     */
    updateSystemStatus(data) {
      if (data.mode !== undefined) {
        this.systemStatus.mode = data.mode
      }
      if (data.battery !== undefined) {
        this.systemStatus.battery = data.battery
      }
    },
    
    /**
     * 更新系统模式（实时/回放）
     */
    updateSystemMode(mode) {
      console.log('[Store] 系统模式切换:', mode)
      this.systemMode = mode
      this.addLog(`系统模式切换为: ${mode === 'REALTIME' ? '实时模式' : '回放模式'}`, 'info')
    },

    applyFlightStateUpdate(data = {}, timestamp = Date.now()) {
      this.realtimeViews.flightState = {
        ...this.realtimeViews.flightState,
        ...data,
        raw: data.raw || this.realtimeViews.flightState.raw || {}
      }
      this.realtimeViews.updatedAt = timestamp

      this.updateFlightState({
        states_lat: data.latitude,
        states_lon: data.longitude,
        states_height: data.height,
        states_Vx_GS: data.vx,
        states_Vy_GS: data.vy,
        states_Vz_GS: data.vz,
        states_p: data.raw?.states_p ?? data.p_rate,
        states_q: data.raw?.states_q ?? data.q_rate,
        states_r: data.raw?.states_r ?? data.r_rate,
        states_phi: data.raw?.states_phi ?? data.phi,
        states_theta: data.raw?.states_theta ?? data.theta,
        states_psi: data.raw?.states_psi ?? data.psi
      })
    },

    applyPlanningStateUpdate(data = {}, timestamp = Date.now()) {
      this.realtimeViews.planningState = {
        ...this.realtimeViews.planningState,
        ...data
      }
      this.realtimeViews.updatedAt = timestamp
      this.experimentContext.missionPhase = this._buildMissionPhase(data.mission_id)

      this.updateGCSData({
        Tele_GCS_CmdIdx: data.cmd_idx,
        Tele_GCS_Mission: data.mission_id,
        Tele_GCS_Val: data.mission_value,
        Tele_GCS_com_GCS_fail: data.gcs_link_fail ? 1 : 0
      })

      this.updateAvoiFlag({
        AvoiFlag_LaserRadar_Enabled: data.avoid_enabled,
        AvoiFlag_AvoidanceFlag: data.avoid_triggered,
        AvoiFlag_GuideFlag: data.guide_flag
      })

      this.planningTelemetry.status = this._safeNumber(data.planning_status, 0)
      this.planningTelemetry.globalPathCount = this._safeNumber(data.global_path_count, 0)
      this.planningTelemetry.localTrajCount = this._safeNumber(data.local_traj_count, 0)
      this.planningTelemetry.obstacleCount = this._safeNumber(data.obstacle_count, 0)
      if (data.current_pos_x !== undefined) this.planningTelemetry.currentPosX = this._safeNumber(data.current_pos_x, 0)
      if (data.current_pos_y !== undefined) this.planningTelemetry.currentPosY = this._safeNumber(data.current_pos_y, 0)
      if (data.current_pos_z !== undefined) this.planningTelemetry.currentPosZ = this._safeNumber(data.current_pos_z, 0)

      if (Array.isArray(data.global_path) || Array.isArray(data.local_path) || Array.isArray(data.local_traj) || Array.isArray(data.obstacles)) {
        this.updatePlanningTelemetry(data)
      }

      const actualPoint = this._updateActualPoseFromTelemetry(timestamp)
      if (!actualPoint) {
        const fallbackPoint = this._buildPlanningFallbackPose(timestamp)
        if (fallbackPoint) {
          this.actualPose = fallbackPoint
          this.addTrajectoryPoint(fallbackPoint.x, fallbackPoint.y, fallbackPoint.z, timestamp)
        }
      }

      this._pushMetricTrend('obstacleCount', this.planningTelemetry.obstacleCount)
    },

    applySystemPerformanceUpdate(data = {}, timestamp = Date.now()) {
      this.realtimeViews.systemPerformance = {
        ...this.realtimeViews.systemPerformance,
        esc_power_pct: data.esc_power_pct ?? data.esc_power_pct_avg ?? this.realtimeViews.systemPerformance.esc_power_pct,
        esc_power_pct_avg: data.esc_power_pct_avg ?? data.esc_power_pct ?? this.realtimeViews.systemPerformance.esc_power_pct_avg,
        trusted: {
          ...(this.realtimeViews.systemPerformance.trusted || {}),
          ...(data.trusted || {})
        },
        derived: {
          ...(this.realtimeViews.systemPerformance.derived || {}),
          ...(data.derived || {})
        },
        metric_quality: {
          ...(this.realtimeViews.systemPerformance.metric_quality || {}),
          ...(data.metric_quality || {})
        },
        ...data
      }
      this.realtimeViews.updatedAt = timestamp

      this._pushMetricTrend('planningTimeMs', this.realtimeViews.systemPerformance.planning_time_ms, this.realtimeViews.updatedAt)
      this._pushMetricTrend('controlJitterMs', this.realtimeViews.systemPerformance.control_jitter_ms, this.realtimeViews.updatedAt)
      this._pushMetricTrend('trackingRmse', this.realtimeViews.systemPerformance.tracking_rmse, this.realtimeViews.updatedAt)
      this._pushMetricTrend('obstacleCount', this.realtimeViews.systemPerformance.obstacle_count, this.realtimeViews.updatedAt)
    },

    applyCaptureOverviewUpdate(message = {}) {
      const payload = message?.data || {}
      this.captureState = {
        ...this.captureState,
        recording: !!payload.recording,
        inputPorts: payload.enabled_ports || [],
        flightControlRateHz: this._safeNumber(payload.flight_control_rate_hz, 0),
        planningRateHz: this._safeNumber(payload.planning_rate_hz, 0),
        radarRateHz: this._safeNumber(payload.radar_rate_hz, 0),
        perceptionRateHz: this._safeNumber(payload.perception_rate_hz, 0),
        packetCounts: payload.packet_counts || {},
        lastPacketTs: payload.last_packet_ts || null,
        parseErrorCount: this._safeNumber(payload.parse_error_count, 0),
        lastError: payload.last_error || '',
        outputDir: payload.output_dir || this.captureState.outputDir,
        bytesWritten: this._safeNumber(payload.bytes_written, 0)
      }

      if (message.case_id) {
        this.experimentContext.caseId = message.case_id
      }

      this.refreshDerivedAnalysisState()
    },

    applyDataQualityUpdate(message = {}) {
      const payload = message?.data || {}
      this.dataQuality = {
        ...this.dataQuality,
        parseErrorCount: this._safeNumber(payload.parse_error_count, 0),
        windowMissingCount: this._safeNumber(payload.window_missing_count, 0),
        planningGapMs: payload.planning_gap_ms ?? null,
        flightControlGapMs: payload.flight_control_gap_ms ?? null,
        radarGapMs: payload.radar_gap_ms ?? null,
        radarMissing: !!payload.radar_missing,
        healthLevel: payload.health_level || 'unknown',
        healthText: payload.health_text || ''
      }

      this.refreshDerivedAnalysisState()
    },

    applyKPIUpdate(message = {}) {
      const payload = message?.data || {}
      const timestamp = message?.timestamp || Date.now()
      const dimensions = payload.dimensions || {}

      this.kpiSummary.dimensions = {
        computing: dimensions.computing || null,
        communication: dimensions.communication || null,
        energy: dimensions.energy || null,
        mission: dimensions.mission || null,
        performance: dimensions.performance || null
      }
      this.kpiSummary.indicators = payload.indicators || {}
      this.kpiSummary.windowMetrics = payload.window_metrics || {}
      this.kpiSummary.overallScore = payload.overallScore ?? payload.overall_score ?? null
      this.kpiSummary.updatedAt = timestamp

      Object.entries(this.kpiSummary.dimensions).forEach(([key, value]) => {
        if (!value) {
          return
        }
        this._pushBoundedHistory(key, {
          ...value,
          timestamp
        })
      })

      if (payload.views?.flight_state) {
        this.applyFlightStateUpdate(payload.views.flight_state, timestamp)
      }
      if (payload.views?.planning_state) {
        this.applyPlanningStateUpdate(payload.views.planning_state, timestamp)
      }
      if (payload.views?.system_performance) {
        this.applySystemPerformanceUpdate(payload.views.system_performance, timestamp)
      }
    },

    applyExperimentContextUpdate(payload = {}) {
      const runtime = payload?.data || payload?.runtime || payload || {}
      const caseData = runtime.case || {}
      const taskData = runtime.task || {}
      const scenarioData = runtime.scenario || {}
      const architectureData = runtime.architecture || {}
      const architectureProfiles = runtime.architecture_profiles || payload?.architecture_profiles || {}
      const figureContext = this._extractFigureSemantics(runtime, caseData, runtime.figure_semantics, payload)

      if (!Object.keys(caseData).length && !Object.keys(taskData).length && !Object.keys(scenarioData).length && !Object.keys(figureContext).length) {
        return
      }

      if (caseData.recording_case_id) {
        this.experimentContext.caseId = caseData.recording_case_id
      }
      if (caseData.case_id) {
        this.experimentContext.planCaseId = caseData.case_id
        this.experimentContext.selectedPlanCaseId = caseData.case_id
      }

      this.experimentContext.caseMeta = {
        repeatIndex: caseData.repeat_index ?? this.experimentContext.caseMeta.repeatIndex,
        durationSec: caseData.duration_sec ?? this.experimentContext.caseMeta.durationSec,
        evaluationWindowSec: caseData.evaluation_window_sec ?? this.experimentContext.caseMeta.evaluationWindowSec
      }

      this.experimentContext.task = {
        plannedCmdIdx: this._safeNumber(taskData.planned_cmd_idx, this.experimentContext.task.plannedCmdIdx),
        effectiveCmdIdx: this._safeNumber(taskData.effective_cmd_idx, this.experimentContext.task.effectiveCmdIdx),
        missionId: this._safeNumber(taskData.mission_id, this.experimentContext.task.missionId),
        taskName: taskData.task_name || this.experimentContext.task.taskName,
        taskGroup: taskData.task_group || this.experimentContext.task.taskGroup,
        phase: taskData.phase || this.experimentContext.task.phase,
        source: taskData.source || this.experimentContext.task.source
      }

      this.experimentContext.architecture = {
        architectureId: architectureData.architecture_id || this.experimentContext.architecture.architectureId,
        displayName: architectureData.display_name || this.experimentContext.architecture.displayName,
        mappingProfile: architectureData.mapping_profile || this.experimentContext.architecture.mappingProfile,
        adaptationMode: architectureData.adaptation_mode || this.experimentContext.architecture.adaptationMode,
        focus: architectureData.focus || this.experimentContext.architecture.focus
      }

      this.experimentContext.architectureProfiles = {
        baselineProfiles: architectureProfiles.baseline_profiles || architectureProfiles.baselineProfiles || this.experimentContext.architectureProfiles.baselineProfiles,
        candidateProfiles: architectureProfiles.candidate_profiles || architectureProfiles.candidateProfiles || this.experimentContext.architectureProfiles.candidateProfiles,
        researchProfiles: architectureProfiles.research_profiles || architectureProfiles.researchProfiles || this.experimentContext.architectureProfiles.researchProfiles
      }

      this.experimentContext.scenarioId = scenarioData.scenario_id || this.experimentContext.scenarioId
      this.experimentContext.scenarioName = scenarioData.display_name || this.experimentContext.scenarioName
      this.experimentContext.scenarioSource = scenarioData.source || this.experimentContext.scenarioSource
      this.experimentContext.scenarioConfidence = this._safeNumber(scenarioData.confidence, this.experimentContext.scenarioConfidence)
      this.experimentContext.environmentClass = scenarioData.environment_class || this.experimentContext.environmentClass
      this.experimentContext.obstacleDensity = scenarioData.obstacle_density || this.experimentContext.obstacleDensity
      this.experimentContext.windLevel = scenarioData.wind_level || this.experimentContext.windLevel
      this.experimentContext.linkQualityLevel = scenarioData.link_quality || this.experimentContext.linkQualityLevel
      this.experimentContext.sensorQualityLevel = scenarioData.sensor_quality || this.experimentContext.sensorQualityLevel
      this.experimentContext.disturbanceTags = scenarioData.disturbance_tags || this.experimentContext.disturbanceTags
      this.experimentContext.heuristicTags = scenarioData.heuristic_tags || this.experimentContext.heuristicTags
      this.experimentContext.triggerPolicy = runtime.trigger_policy || this.experimentContext.triggerPolicy
      this.experimentContext.missionPhase = taskData.phase || this.experimentContext.missionPhase
      this.experimentContext.updatedAt = Date.now()
      this._applyFigureContext(figureContext)

      if (!this.architectureRecommendation.currentArchitecture) {
        this.architectureRecommendation.currentArchitecture = this.experimentContext.architecture.displayName
      }

      this.refreshDerivedAnalysisState()
    },

    applyRecordingStatus(payload) {
      const sessionInfo = payload?.session_info || {}
      const recordingData = payload?.data || {}
      const figureContext = this._extractFigureSemantics(payload, sessionInfo, recordingData)
      this.dataRecording.enabled = payload?.is_active ?? !!recordingData.recording
      this.dataRecording.sessionId = payload?.session_id || sessionInfo.session_id || ''
      this.dataRecording.recordingStartTime = sessionInfo.start_time
        ? Math.round(sessionInfo.start_time * 1000)
        : (this.dataRecording.enabled ? this.dataRecording.recordingStartTime : null)
      this.dataRecording.recordFilePath = sessionInfo.data_directory || recordingData.output_dir || ''
      this.dataRecording.recordCount = sessionInfo.data_counters?.raw_records || sessionInfo.data_counters?.bus_traffic || 0
      this.dataRecording.totalBytes = sessionInfo.total_bytes || recordingData.bytes_written || 0
      this.dataRecording.functionStats = sessionInfo.func_stats || []
      this.dataRecording.lastRecordTime = Date.now()
      this.experimentContext.caseId = payload?.case_id || sessionInfo.case_id || this._buildCaseId(this.dataRecording.sessionId)
      this._applyFigureContext(figureContext)
      this.applyFigureAssetStatusUpdate(figureContext)
      if (payload?.experiment_context) {
        this.applyExperimentContextUpdate(payload.experiment_context)
      }
      if (payload?.pipeline_status) {
        this.applyPipelineStatusUpdate(payload.pipeline_status)
      }

      this.refreshDerivedAnalysisState()
    },

    applyPipelineStatusUpdate(message = {}) {
      const payload = message?.data || message || {}
      this.pipelineStatus = {
        ...this.pipelineStatus,
        rawRecordingStatus: payload.raw_recording_status || this.pipelineStatus.rawRecordingStatus,
        standardFilesStatus: payload.standard_files_status || this.pipelineStatus.standardFilesStatus,
        dsmStatus: payload.dsm_status || this.pipelineStatus.dsmStatus,
        evaluationStatus: payload.evaluation_status || this.pipelineStatus.evaluationStatus,
        optimizationStatus: payload.optimization_status || this.pipelineStatus.optimizationStatus,
        archiveStatus: payload.archive_status || this.pipelineStatus.archiveStatus,
        figureAssetReady: payload.figure_asset_ready ?? this.pipelineStatus.figureAssetReady,
        figureBatchManifestPath: payload.figure_batch_manifest_path ?? this.pipelineStatus.figureBatchManifestPath,
        standardFiles: {
          ...this.pipelineStatus.standardFiles,
          ...(payload.standard_files || {})
        },
        updatedAt: Date.now()
      }
      this.applyFigureAssetStatusUpdate(payload)
    },

    applyDsmSummaryUpdate(message = {}) {
      const payload = message?.data || message || {}
      const figurePatch = this._applyFigureContext(this._extractFigureSemantics(payload))
      this.dsmSummary = {
        nodeCount: payload.node_count ?? this.dsmSummary.nodeCount,
        edgeCount: payload.edge_count ?? this.dsmSummary.edgeCount,
        crossModuleInteractions: payload.cross_module_interactions ?? this.dsmSummary.crossModuleInteractions,
        totalBusBytes: payload.total_bus_bytes ?? this.dsmSummary.totalBusBytes,
        avgCrossLatency: payload.avg_cross_latency ?? this.dsmSummary.avgCrossLatency,
        globalStatsReady: !!(payload.global_stats_ready ?? this.dsmSummary.globalStatsReady),
        ...figurePatch,
        updatedAt: Date.now()
      }
      this.applyFigureAssetStatusUpdate(payload)
    },

    applyEvaluationSummaryUpdate(message = {}) {
      const payload = message?.data || message || {}
      const figurePatch = this._applyFigureContext(this._extractFigureSemantics(payload))
      this.evaluationSummary = {
        baselineAllocationId: payload.baseline_allocation_id ?? this.evaluationSummary.baselineAllocationId,
        candidateAllocationId: payload.candidate_allocation_id ?? this.evaluationSummary.candidateAllocationId,
        finalCompositeScore: payload.final_composite_score ?? this.evaluationSummary.finalCompositeScore,
        constraintViolationCount: payload.constraint_violation_count ?? this.evaluationSummary.constraintViolationCount,
        domainScores: payload.domain_scores || this.evaluationSummary.domainScores,
        baselineDelta: payload.baseline_delta || this.evaluationSummary.baselineDelta,
        evaluationReady: !!(payload.evaluation_ready ?? this.evaluationSummary.evaluationReady),
        ...figurePatch,
        updatedAt: Date.now()
      }
      this.applyFigureAssetStatusUpdate(payload)
    },

    applyArchitectureRecommendationUpdate(message = {}) {
      const payload = message?.data || message || {}
      const figurePatch = this._applyFigureContext(this._extractFigureSemantics(payload))
      const currentArchitectureDetail = payload.current_architecture || payload.currentArchitecture || {}
      const recommendedArchitectureDetail = payload.recommended_architecture || payload.recommendedArchitecture || {}
      const candidateSummaries = payload.all_candidate_summaries || payload.candidates || payload.candidate_summaries || this.architectureRecommendation.candidates
      const currentArchitecture = typeof currentArchitectureDetail === 'string'
        ? currentArchitectureDetail
        : currentArchitectureDetail.profile_name || currentArchitectureDetail.display_name || currentArchitectureDetail.name || this.experimentContext.architecture.displayName || this.architectureRecommendation.currentArchitecture
      const recommendedArchitecture = typeof recommendedArchitectureDetail === 'string'
        ? recommendedArchitectureDetail
        : recommendedArchitectureDetail.profile_name || recommendedArchitectureDetail.display_name || recommendedArchitectureDetail.name || this.architectureRecommendation.recommendedArchitecture

      this.architectureRecommendation = {
        currentArchitecture,
        recommendedArchitecture,
        scoreDelta: payload.score_delta ?? payload.expected_score_delta ?? payload.predicted_score_delta ?? this.architectureRecommendation.scoreDelta,
        crossCountDelta: payload.cross_count_delta ?? payload.predicted_cross_count_delta ?? this.architectureRecommendation.crossCountDelta,
        powerDelta: payload.power_delta ?? payload.predicted_power_delta ?? this.architectureRecommendation.powerDelta,
        constraintPass: payload.constraint_pass ?? this.architectureRecommendation.constraintPass,
        riskText: payload.risk_explanations || payload.risk_text || this.architectureRecommendation.riskText,
        triggerEvidence: payload.trigger_evidence || payload.evidence || this.architectureRecommendation.triggerEvidence,
        candidates: candidateSummaries,
        ...figurePatch,
        updatedAt: Date.now()
      }
      this.applyFigureAssetStatusUpdate(payload)
    },

    applyFigureAssetStatusUpdate(message = {}) {
      const payload = message?.data || message || {}
      const figurePatch = this._applyFigureContext(this._extractFigureSemantics(payload))

      if (!Object.keys(figurePatch).length) {
        return
      }

      this.figureAssetStatus = {
        ...this.figureAssetStatus,
        ...figurePatch,
        figureAssetReady: figurePatch.figureAssetReady ?? this.figureAssetStatus.figureAssetReady,
        figureBatchManifestPath: figurePatch.figureBatchManifestPath ?? this.figureAssetStatus.figureBatchManifestPath,
        updatedAt: Date.now()
      }

      this.pipelineStatus = {
        ...this.pipelineStatus,
        figureAssetReady: this.figureAssetStatus.figureAssetReady,
        figureBatchManifestPath: this.figureAssetStatus.figureBatchManifestPath,
        updatedAt: Date.now()
      }
    },

    refreshDerivedAnalysisState() {
      const hasSession = !!this.dataRecording.sessionId
      const hasFlight = this.captureState.flightControlRateHz > 0 || this.history.rollActual.length > 1 || this.history.pwm1.length > 1
      const hasPlanning = this.captureState.planningRateHz > 0 || this.planningTelemetry.seqId > 0 || this.globalPath.length > 0 || this.localTraj.length > 0
      const hasRadar = this.captureState.radarRateHz > 0 || this.planningTelemetry.obstacleCount > 0 || this.obstacles.length > 0
      const hasPerception = this.captureState.perceptionRateHz > 0

      const nextStandardFiles = {
        fcsTelemetry: hasFlight ? 'raw_only' : 'missing',
        planningTelemetry: hasPlanning ? 'raw_only' : 'missing',
        radarData: hasRadar ? 'raw_only' : 'missing',
        busTraffic: 'missing',
        cameraData: hasPerception ? 'raw_only' : 'missing'
      }

      const rawRecordingStatus = this.dataRecording.enabled
        ? 'running'
        : hasSession
          ? 'ready'
          : 'waiting'

      const standardFilesStatus = Object.values(nextStandardFiles).every((value) => value === 'ready')
        ? 'ready'
        : hasSession
          ? 'missing'
          : 'waiting'

      this.pipelineStatus = {
        ...this.pipelineStatus,
        rawRecordingStatus,
        standardFilesStatus: this.pipelineStatus.standardFilesStatus === 'ready' ? 'ready' : standardFilesStatus,
        standardFiles: {
          fcsTelemetry: this.pipelineStatus.standardFiles.fcsTelemetry === 'ready' ? 'ready' : nextStandardFiles.fcsTelemetry,
          planningTelemetry: this.pipelineStatus.standardFiles.planningTelemetry === 'ready' ? 'ready' : nextStandardFiles.planningTelemetry,
          radarData: this.pipelineStatus.standardFiles.radarData === 'ready' ? 'ready' : nextStandardFiles.radarData,
          busTraffic: this.pipelineStatus.standardFiles.busTraffic === 'ready' ? 'ready' : nextStandardFiles.busTraffic,
          cameraData: this.pipelineStatus.standardFiles.cameraData === 'ready' ? 'ready' : nextStandardFiles.cameraData
        },
        updatedAt: Date.now()
      }

      const evidence = []
      const perf = this.realtimeViews.systemPerformance || {}
      const standardFileStates = Object.values(this.pipelineStatus.standardFiles || {})
      const emptyFileCount = standardFileStates.filter((value) => value === 'empty').length
      const missingFileCount = standardFileStates.filter((value) => value === 'missing').length
      if (Number.isFinite(Number(perf.planning_time_ms)) && Number(perf.planning_time_ms) > 0) {
        evidence.push(`planning ${Number(perf.planning_time_ms).toFixed(1)} ms`)
      }
      if (Number.isFinite(Number(perf.obstacle_count)) && Number(perf.obstacle_count) > 0) {
        evidence.push(`obstacles ${Math.round(Number(perf.obstacle_count))}`)
      }
      if (this.dataQuality.healthLevel && this.dataQuality.healthLevel !== 'unknown') {
        evidence.push(`quality ${this.dataQuality.healthLevel}`)
      }
      if (emptyFileCount > 0) {
        evidence.push(`${emptyFileCount} standard files empty`)
      } else if (missingFileCount > 0 || this.pipelineStatus.standardFilesStatus !== 'ready') {
        evidence.push(`${missingFileCount || 5} standard files missing`)
      }

      const fallbackRiskText = this.pipelineStatus.standardFilesStatus === 'ready'
        ? '标准文件已就绪，但 DSM 和评估结果还未形成可比较的推荐输出。'
        : this.pipelineStatus.standardFilesStatus === 'empty'
          ? '标准文件已生成，但当前只有表头没有有效数据行，不能形成可用的架构分析结果。'
          : '尚未导出 thesis-compatible 五类标准文件，当前不能形成有效架构分析依据。'

      const hasRecommendation = !!this.architectureRecommendation.recommendedArchitecture

      const currentArchitecture = this.experimentContext.architecture.displayName || this.architectureRecommendation.currentArchitecture || 'Baseline Balanced'
      const candidateProfiles = this.experimentContext.architectureProfiles.candidateProfiles || []
      const baselineProfiles = this.experimentContext.architectureProfiles.baselineProfiles || []
      const placeholderCandidates = [...baselineProfiles, ...candidateProfiles].slice(0, 3).map((profile) => ({
        id: profile.profile_id,
        name: profile.profile_name,
        group: profile.profile_group,
        status: 'awaiting_evaluation'
      }))

      this.architectureRecommendation = {
        ...this.architectureRecommendation,
        currentArchitecture,
        recommendedArchitecture: this.architectureRecommendation.recommendedArchitecture || '',
        riskText: hasRecommendation
          ? (this.architectureRecommendation.riskText || fallbackRiskText)
          : fallbackRiskText,
        triggerEvidence: hasRecommendation && this.architectureRecommendation.triggerEvidence.length
          ? this.architectureRecommendation.triggerEvidence
          : evidence,
        candidates: this.architectureRecommendation.candidates.length
          ? this.architectureRecommendation.candidates
          : placeholderCandidates,
        updatedAt: Date.now()
      }
    },

    async fetchExperimentPlan() {
      try {
        const response = await backend.experiment.getPlan()
        const cases = response?.cases || []
        this.experimentContext.availableCases = cases
        const selectedCaseId = response?.selected_case_id || this.experimentContext.selectedPlanCaseId || cases[0]?.case_id || ''
        this.experimentContext.selectedPlanCaseId = selectedCaseId
        if (!this.experimentContext.planCaseId && selectedCaseId) {
          this.experimentContext.planCaseId = selectedCaseId
        }
        return response
      } catch (error) {
        this.addLog(`获取实验矩阵失败: ${error.message}`, 'warning')
        return null
      }
    },

    async fetchExperimentRuntime() {
      try {
        const response = await backend.experiment.getRuntime()
        if (response?.runtime) {
          this.applyExperimentContextUpdate(response)
        }
        if (response?.selected_case_id) {
          this.experimentContext.selectedPlanCaseId = response.selected_case_id
        }
        return response
      } catch (error) {
        this.addLog(`获取实验运行态失败: ${error.message}`, 'warning')
        return null
      }
    },

    async selectExperimentCase(caseId) {
      if (!caseId) {
        return null
      }
      try {
        const response = await backend.experiment.selectCase({ case_id: caseId })
        this.experimentContext.selectedPlanCaseId = response?.selected_case_id || caseId
        this.applyExperimentContextUpdate(response)
        return response
      } catch (error) {
        this.addLog(`切换实验 case 失败: ${error.message}`, 'warning')
        throw error
      }
    },

    async fetchRecordingStatus() {
      try {
        const status = await backend.recording.getStatus()
        this.applyRecordingStatus(status)
        return status
      } catch (error) {
        this.addLog(`获取录制状态失败: ${error.message}`, 'warning')
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
        this.addLog(`获取UDP状态失败: ${error.message}`, 'warning')
        return null
      }
    },

    async startFullRecording(config = {}) {
      try {
        const startConfig = {
          ...config,
          plan_case_id: config.plan_case_id || this.experimentContext.selectedPlanCaseId || undefined
        }
        const response = await backend.recording.startRecording(startConfig)
        this.applyRecordingStatus({
          is_active: true,
          session_id: response.session_id,
          session_info: response.session_info,
          experiment_context: response.experiment_context
        })
        this.addLog('开始全量录制', 'info')
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
          session_info: response.session_info,
          experiment_context: response.experiment_context
        })
        this.addLog('停止全量录制', 'info')
        return response
      } catch (error) {
        this.addLog(`停止录制失败: ${error.message}`, 'error')
        throw error
      }
    },
    
    /**
     * 更新回放状态
     */
    updateReplayStatus(data) {
      console.log('[Store] 回放状态更新:', data)
      
      if (data.is_loaded !== undefined) {
        this.replayStatus.is_loaded = data.is_loaded
      }
      if (data.is_playing !== undefined) {
        this.replayStatus.is_playing = data.is_playing
      }
      if (data.replay_active !== undefined) {
        this.replayStatus.replay_active = data.replay_active
      }
      if (data.current_file !== undefined) {
        this.replayStatus.current_file = data.current_file
      }
      if (data.current_idx !== undefined) {
        this.replayStatus.current_idx = data.current_idx
      }
      if (data.total_rows !== undefined) {
        this.replayStatus.total_rows = data.total_rows
      }
      if (data.total_time !== undefined) {
        this.replayStatus.total_time = data.total_time
      }
      if (data.speed !== undefined) {
        this.replayStatus.speed = data.speed
      }
      if (data.progress !== undefined) {
        this.replayStatus.progress = data.progress
      }
      if (data.current_time !== undefined) {
        this.replayStatus.current_time = data.current_time
      }
    },
    
    /**
     * 回放分析 - 获取变量列表
     */
    async fetchHeaders() {
      try {
        this.replayAnalysis.loading = true
        this.replayAnalysis.error = null
        
        const response = await fetch(buildApiUrl('/api/replay/headers'))
        const data = await response.json()
        
        if (data.type === 'replay_headers' && data.headers) {
          this.replayAnalysis.allVariables = data.headers
          // 对变量进行分类
          this.categorizeVariables(data.headers)
          console.log('[Store] 回放变量列表:', this.replayAnalysis.allVariables)
        }
      } catch (error) {
        console.error('获取回放变量失败:', error)
        this.replayAnalysis.error = error.message
      } finally {
        this.replayAnalysis.loading = false
      }
    },
    
    /**
     * 回放分析 - 对变量进行分类
     */
    categorizeVariables(variables) {
      const categories = {
        'PWMS': [],
        'STATES': [],
        'DATACTRL': [],
        'GNCBUS': [],
        'AVOIFLAG': [],
        'DATAFUTABA': [],
        'DATAGCS': [],
        'PARAM': [],
        'ESC': []
      }
      
      for (const variable of variables) {
        const upperVar = variable.toUpperCase()
        
        if (upperVar.includes('PWM') || upperVar.startsWith('PWM')) {
          categories['PWMS'].push(variable)
        } else if (upperVar.includes('STATE') || upperVar.includes('LAT') || upperVar.includes('LON') || upperVar.includes('HEIGHT')) {
          categories['STATES'].push(variable)
        } else if (upperVar.includes('CTRL') || upperVar.includes('REF_') || upperVar.includes('EST_')) {
          categories['DATACTRL'].push(variable)
        } else if (upperVar.includes('GNC') || upperVar.includes('CMDVALUE')) {
          categories['GNCBUS'].push(variable)
        } else if (upperVar.includes('AVOI') || upperVar.includes('FLAG')) {
          categories['AVOIFLAG'].push(variable)
        } else if (upperVar.includes('FUTABA') || upperVar.includes('FTB')) {
          categories['DATAFUTABA'].push(variable)
        } else if (upperVar.includes('GCS') || upperVar.includes('TELE')) {
          categories['DATAGCS'].push(variable)
        } else if (upperVar.includes('PARAM')) {
          categories['PARAM'].push(variable)
        } else if (upperVar.includes('ESC') || upperVar.includes('RPM')) {
          categories['ESC'].push(variable)
        }
      }
      
      this.replayAnalysis.categorizedVars = categories
    },
    
    /**
     * 回放分析 - 切换变量选择
     */
    toggleVariable(variable, isSelected) {
      const index = this.replayAnalysis.selectedVariables.indexOf(variable)
      if (isSelected && index === -1) {
        this.replayAnalysis.selectedVariables.push(variable)
      } else if (!isSelected && index !== -1) {
        this.replayAnalysis.selectedVariables.splice(index, 1)
      }
    },
    
    /**
     * 回放分析 - 获取图表数据
     */
    async fetchChartSeries(variables) {
      try {
        this.replayAnalysis.loading = true
        this.replayAnalysis.error = null
        
        const response = await fetch(buildApiUrl('/api/replay/chart'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ variables })
        })
        
        const data = await response.json()
        
        if (data.type === 'replay_chart_data' && data.data) {
          this.replayAnalysis.timeAxis = data.data.timeAxis || []
          this.replayAnalysis.seriesData = data.data.seriesData || {}
          this.replayAnalysis.hasData = true
          console.log('[Store] 回放图表数据加载成功')
        }
      } catch (error) {
        console.error('获取回放图表数据失败:', error)
        this.replayAnalysis.error = error.message
      } finally {
        this.replayAnalysis.loading = false
      }
    },
    
    /**
     * 添加回放状态数据监听
     * 处理来自后端的 replay_analysis_data 消息
     */
    handleReplayAnalysisData(data) {
      if (data.timeAxis) {
        this.replayAnalysis.timeAxis = data.timeAxis
      }
      if (data.seriesData) {
        this.replayAnalysis.seriesData = data.seriesData
      }
      if (data.headers) {
        this.replayAnalysis.allVariables = data.headers
        this.categorizeVariables(data.headers)
      }
      this.replayAnalysis.hasData = true
    },
    
    /**
     * 发送WebSocket消息
     * 用于发送回放控制命令等
     */
    sendWebSocketMessage(message) {
      if (!wsInstance) {
        console.error('[Store] WebSocket未连接，无法发送消息')
        return false
      }
      
      try {
        const messageString = typeof message === 'string'
          ? message
          : JSON.stringify(message)
        
        const success = wsInstance.send(messageString)
        
        if (success) {
          console.log('[Store] WebSocket消息已发送:', message)
        } else {
          console.error('[Store] 发送WebSocket消息失败')
        }
        
        return success
      } catch (error) {
        console.error('[Store] 发送WebSocket消息异常:', error)
        return false
      }
    },
    
    
    /**
     * 发送 WebSocket 消息
     */
    sendWebSocketMessage(message) {
      if (wsInstance && this.connected) {
        wsInstance.send(message)
      } else {
        console.warn('[Store] WebSocket 未连接，无法发送消息:', message)
      }
    },
    
    /**
     * 添加历史数据（用于图表显示）
     */
    addHistoryData(category, data) {
      const timestamp = Date.now()
      const maxPoints = 500
      
      switch (category) {
        case 'flightState':
          // 新格式 - fcsStates结构体数据
          if (data.states_phi !== undefined || data.roll !== undefined) {
            const phi = data.states_phi !== undefined ? this._safeNumber(data.states_phi) : this._normalizeAngleToDegrees(data.roll ?? this.attitude.roll)
            this.history.rollActual.push({ value: phi, timestamp })
          }
          if (data.states_theta !== undefined || data.pitch !== undefined) {
            const theta = data.states_theta !== undefined ? this._safeNumber(data.states_theta) : this._normalizeAngleToDegrees(data.pitch ?? this.attitude.pitch)
            this.history.pitchActual.push({ value: theta, timestamp })
          }
          if (data.states_psi !== undefined || data.yaw !== undefined) {
            const psi = data.states_psi !== undefined ? this._safeNumber(data.states_psi) : this._normalizeAngleToDegrees(data.yaw ?? this.attitude.yaw)
            this.history.yawActual.push({ value: psi, timestamp })
          }
          if (data.states_height !== undefined || data.altitude !== undefined) {
            const height = data.states_height ?? data.altitude ?? this.fcsStates.states_height
            this.history.altitudeActual.push({ value: height, timestamp })
          }
          if (data.states_Vx_GS !== undefined || data.velocity_x !== undefined) {
            const vx = data.states_Vx_GS ?? data.velocity_x ?? this.fcsStates.states_Vx_GS
            this.history.velocityX.push({ value: vx, timestamp })
          }
          if (data.states_Vy_GS !== undefined || data.velocity_y !== undefined) {
            const vy = data.states_Vy_GS ?? data.velocity_y ?? this.fcsStates.states_Vy_GS
            this.history.velocityY.push({ value: vy, timestamp })
          }
          if (data.states_Vz_GS !== undefined || data.velocity_z !== undefined) {
            const vz = data.states_Vz_GS ?? data.velocity_z ?? this.fcsStates.states_Vz_GS
            this.history.velocityZ.push({ value: vz, timestamp })
          }
          if (data.states_p !== undefined || data.angular_velocity_x !== undefined) {
            const p = data.states_p ?? data.angular_velocity_x ?? this.fcsStates.states_p
            this._pushHistoryPoint('angularRateP', p, timestamp, maxPoints)
          }
          if (data.states_q !== undefined || data.angular_velocity_y !== undefined) {
            const q = data.states_q ?? data.angular_velocity_y ?? this.fcsStates.states_q
            this._pushHistoryPoint('angularRateQ', q, timestamp, maxPoints)
          }
          if (data.states_r !== undefined || data.angular_velocity_z !== undefined) {
            const r = data.states_r ?? data.angular_velocity_z ?? this.fcsStates.states_r
            this._pushHistoryPoint('angularRateR', r, timestamp, maxPoints)
          }
          break

        case 'gncBus':
          this._pushHistoryPoint('tokenRud', data.GNCBus_TokenMode_rud_state ?? this.gncBus.GNCBus_TokenMode_rud_state, timestamp, maxPoints)
          this._pushHistoryPoint('tokenAil', data.GNCBus_TokenMode_ail_state ?? this.gncBus.GNCBus_TokenMode_ail_state, timestamp, maxPoints)
          this._pushHistoryPoint('tokenEle', data.GNCBus_TokenMode_ele_state ?? this.gncBus.GNCBus_TokenMode_ele_state, timestamp, maxPoints)
          this._pushHistoryPoint('tokenCol', data.GNCBus_TokenMode_col_state ?? this.gncBus.GNCBus_TokenMode_col_state, timestamp, maxPoints)
          break

        case 'fcsData':
          this._pushHistoryPoint('futabaRoll', data.Tele_ftb_Roll ?? this.fcsData.Tele_ftb_Roll, timestamp, maxPoints)
          this._pushHistoryPoint('futabaPitch', data.Tele_ftb_Pitch ?? this.fcsData.Tele_ftb_Pitch, timestamp, maxPoints)
          this._pushHistoryPoint('futabaYaw', data.Tele_ftb_Yaw ?? this.fcsData.Tele_ftb_Yaw, timestamp, maxPoints)
          break
          
        case 'controlLoop':
          if (data.ref_p !== undefined) {
            this.history.rollTarget.push({ value: data.ref_p, timestamp })
          }
          if (data.est_p !== undefined) {
            this.history.rollActual.push({ value: data.est_p, timestamp })
          }
          if (data.ref_theta !== undefined) {
            this.history.pitchTarget.push({ value: data.ref_theta, timestamp })
          }
          if (data.est_theta !== undefined) {
            this.history.pitchActual.push({ value: data.est_theta, timestamp })
          }
          if (data.ref_h !== undefined) {
            this.history.altitudeTarget.push({ value: data.ref_h, timestamp })
          }
          if (data.est_h !== undefined) {
            this.history.altitudeActual.push({ value: data.est_h, timestamp })
          }
          if (data.ref_vx !== undefined) {
            this.history.speedTarget.push({ value: data.ref_vx, timestamp })
          }
          if (data.est_vx !== undefined) {
            this.history.speedActual.push({ value: data.est_vx, timestamp })
          }
          // 记录控制输出历史
          if (data.ctrl_u1 !== undefined) {
            this.history.controlU1.push({ value: data.ctrl_u1, timestamp })
          }
          if (data.ctrl_u2 !== undefined) {
            this.history.controlU2.push({ value: data.ctrl_u2, timestamp })
          }
          if (data.ctrl_u3 !== undefined) {
            this.history.controlU3.push({ value: data.ctrl_u3, timestamp })
          }
          if (data.ctrl_u4 !== undefined) {
            this.history.controlU4.push({ value: data.ctrl_u4, timestamp })
          }
          break
          
        case 'pwmData':
          // 记录PWM历史数据（新增）
          let pwmArray = Array.isArray(data) ? data : data?.pwms || []
          if (pwmArray.length > 0) {
            pwmArray.forEach((pwm, index) => {
              const key = `pwm${index + 1}`
              if (this.history[key]) {
                this.history[key].push({ value: pwm, timestamp })
              }
            })
          }
          break
      }
      
      // 限制历史数据长度
      for (const key in this.history) {
        if (Array.isArray(this.history[key]) && this.history[key].length > maxPoints) {
          this.history[key] = this.history[key].slice(-maxPoints)
        }
      }
      
      // 记录数据（如果启用记录）
      if (this.dataRecording.enabled) {
        this.recordData(category, data)
      }
    },
    
    /**
     * 格式化指令详情
     */
    _formatCommandDetails(type, params) {
      if (!params) return ''
      try {
        if (type === 'cmd_idx') {
          // 显示 [ID: 名称]
          return `[${params.cmdId}: ${params.name || ''}]`
        }
        if (type === 'cmd_mission') {
          // 显示 [ID: 值]
          return `[${params.cmd_mission}: ${params.value}]`
        }
        if (type === 'set_pids') {
           const keys = Object.keys(params);
           return `[${keys.length}个参数]`
        }
      } catch (e) {
        return ''
      }
      return ''
    },

    /**
     * 发送指令到后端（REST API）
     */
    async sendCommandREST(type, payload) {
      try {
        const response = await fetch(buildApiUrl('/api/command'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            type,
            params: payload
          })
        })
        
        const result = await response.json()
        const details = this._formatCommandDetails(type, payload)
        this.addLog(`指令发送: ${type} ${details} - ${result.status || 'unknown'}`, 'info')
        return result
      } catch (error) {
        console.error('发送REST指令失败:', error)
        this.addLog(`发送指令失败: ${error.message}`, 'error')
        return null
      }
    },
    
    /**
     * 发送指令
     */
    sendCommand(type, payload) {
      if (!this.connected || !wsInstance) {
        console.warn('未连接，无法发送指令')
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
        // 增加WebSocket发送日志
        const details = this._formatCommandDetails(type, payload)
        this.addLog(`指令发送: ${type} ${details}`, 'info')
        console.log('发送指令:', message)
        return true
      } catch (error) {
        console.error('发送指令失败:', error)
        this.addLog(`发送指令失败: ${error.message}`, 'error')
        return false
      }
    },
    
    /**
     * 处理命令响应
     */
    handleCommandResponse(data) {
      console.log('收到命令响应:', data)
      this.addLog(`指令响应: ${data.command} - ${data.status}`, 'info')
    },
    
    /**
     * 添加日志
     */
    addLog(message, level = 'info') {
      const logEntry = {
        id: Date.now(),
        message,
        level,
        timestamp: new Date().toLocaleString()
      }
      
      this.logs.push(logEntry)
      
      // 限制日志长度，最多保留500条
      if (this.logs.length > 500) {
        this.logs.shift()
      }
    },
    
    /**
     * 更新配置
     */
    updateConfig(config) {
      const normalizedConfig = { ...config }
      if (Object.prototype.hasOwnProperty.call(normalizedConfig, 'listenAddress')) {
        normalizedConfig.hostIp = normalizedConfig.listenAddress
      }
      this.config = { ...this.config, ...normalizedConfig }
    },
    
    /**
     * 更新轨迹点
     */
    addTrajectoryPoint(x, y, z, timestamp = Date.now()) {
      const lastPoint = this.trajectory[this.trajectory.length - 1]
      
      // 距离阈值，避免记录过于密集的点
      if (lastPoint) {
        const distance = Math.sqrt(
          Math.pow(x - lastPoint.x, 2) +
          Math.pow(y - lastPoint.y, 2) +
          Math.pow(z - lastPoint.z, 2)
        )
        if (distance < 0.1) {
          return
        }
      }
      
      this.trajectory.push({
        x, y, z,
        timestamp
      })
      
      // 限制轨迹长度，最多保留1000个点
      if (this.trajectory.length > 1000) {
        this.trajectory.shift()
      }
    },
    
    /**
     * 清空日志
     */
    clearLogs() {
      this.logs = []
      this.addLog('日志已清空', 'info')
    },
    
    /**
     * 清空轨迹
     */
    clearTrajectory() {
      this.trajectory = []
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
      this.actualFlightOrigin = {
        lat: null,
        lon: null,
        alt: null
      }
    },
    
    /**
     * 启动DSM数据记录 (发送指令到后端)
     */
    startDSMRecording() {
      if (!this.connected || !wsInstance) {
        console.warn('未连接，无法启动录制')
        return false
      }
      
      const message = {
        type: 'recording',
        action: 'start'
      }
      
      try {
        wsInstance.send(JSON.stringify(message))
        this.dataRecording.enabled = true
        this.addLog('发送开始录制指令', 'info')
        return true
      } catch (error) {
        console.error('发送录制指令失败:', error)
        return false
      }
    },
    
    /**
     * 停止DSM数据记录 (发送指令到后端)
     */
    stopDSMRecording() {
      if (!this.connected || !wsInstance) {
        return false
      }
      
      const message = {
        type: 'recording',
        action: 'stop'
      }
      
      try {
        wsInstance.send(JSON.stringify(message))
        this.dataRecording.enabled = false
        this.addLog('发送停止录制指令', 'info')
        return true
      } catch (error) {
        console.error('发送停止指令失败:', error)
        return false
      }
    },

    /**
     * 启动数据记录 (本地模拟 - 已弃用，保留兼容但建议使用startDSMRecording)
     */
    startRecording() {
      // 代理到新的DSM录制
      return this.startDSMRecording()
    },
    
    /**
     * 停止数据记录 (本地模拟 - 已弃用)
     */
    stopRecording() {
      return this.stopDSMRecording()
    },
    
    /**
     * 记录单条数据
     */
    recordData(category, data) {
      if (!this.dataRecording.enabled) {
        return
      }
      
      this.dataRecording.recordCount++
      this.dataRecording.lastRecordTime = Date.now()
      
      // 将数据转换为CSV格式
      const timestamp = new Date().toISOString()
      let csvLine = `${timestamp},${category}`
      
      // 根据不同类型添加不同字段
      switch (category) {
        case 'flightState':
          csvLine += `,${data.roll || 0},${data.pitch || 0},${this.attitude.yaw || 0}`
          csvLine += `,${data.latitude || 0},${data.longitude || 0},${data.altitude || 0}`
          csvLine += `,${data.velocity_x || 0},${data.velocity_y || 0},${data.velocity_z || 0}`
          csvLine += `,${data.angular_velocity_x || 0},${data.angular_velocity_y || 0},${data.angular_velocity_z || 0}`
          break
          
        case 'controlLoop':
          csvLine += `,${data.ref_p || 0},${data.est_p || 0}`
          csvLine += `,${data.ref_theta || 0},${data.est_theta || 0}`
          csvLine += `,${data.ref_h || 0},${data.est_h || 0}`
          csvLine += `,${data.ref_vx || 0},${data.est_vx || 0}`
          csvLine += `,${data.ref_vy || 0},${data.est_vy || 0}`
          csvLine += `,${data.ref_vz || 0},${data.est_vz || 0}`
          csvLine += `,${data.ctrl_u1 || 0},${data.ctrl_u2 || 0},${data.ctrl_u3 || 0},${data.ctrl_u4 || 0}`
          break
          
        case 'avoiflag':
          csvLine += `,${data.laser_radar_enabled || false},${data.avoidance_flag || false},${data.guide_flag || false}`
          break
          
        default:
          csvLine += ','
      }
      
      // 在实际应用中，这里应该将数据发送到后端保存
      // 目前先打印日志
      console.log('[Store] 记录数据:', csvLine)
      
      // TODO: 实现将数据发送到后端API进行保存
      // await this.sendRecordingData(csvLine)
    },
    
    /**
     * 获取记录统计信息
     */
    getRecordingInfo() {
      return {
        enabled: this.dataRecording.enabled,
        startTime: this.dataRecording.recordingStartTime,
        recordCount: this.dataRecording.recordCount,
        lastRecordTime: this.dataRecording.lastRecordTime,
        filePath: this.dataRecording.recordFilePath,
        duration: this.dataRecording.enabled
          ? Math.floor((Date.now() - this.dataRecording.recordingStartTime) / 1000)
          : 0
      }
    }
  }
})