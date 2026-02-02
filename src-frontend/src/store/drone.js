/**
 * Pinia Store - 无人机状态管理
 * 单一数据源，管理所有无人机相关状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

// WebSocket composable
let wsInstance = null

export const useDroneStore = defineStore('drone', {
  state: () => ({
    // ========== 连接状态 ==========
    connected: false,
    connecting: false,
    
    // ========== ExtY_FCS_T 飞控完整数据结构 ==========
    // PWM输出数据 (ExtY_FCS_OUTPUTPWM_T)
    pwms: [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],  // 8个通道的PWM值
    
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
      pos_x: 0,
      pos_y: 0,
      pos_z: 0,
      vel_x: 0,
      vel_y: 0,
      vel_z: 0,
      euler_phi: 0,
      euler_theta: 0,
      euler_psi: 0,
      control_mode: 0,
      flight_mode: 0
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
    
    // ========== 雷达状态 ==========
    lidarStatus: {
      isRunning: false,
      lidarConnected: false,
      imuDataValid: false,
      motionCompActive: false
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
    
    // ========== 航迹数据 ==========
    trajectory: [],     // 历史轨迹点 [{x, y, z, timestamp}]
    globalPath: [],  // 全局路径点 [{x, y, z}]
    localTraj: [],  // 局部轨迹点 [{x, y, z}]
    
    // ========== 障碍物数据 ==========
    obstacles: [],      // 障碍物列表 (Planning Telemetry)
    lidarObstacles: [], // 雷达感知障碍物列表 (ObstacleOutput_T)
    
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
      // PWM历史数据（添加初始默认值）
      pwm1: [{ value: 1000, timestamp: Date.now() }],
      pwm2: [{ value: 1000, timestamp: Date.now() }],
      pwm3: [{ value: 1000, timestamp: Date.now() }],
      pwm4: [{ value: 1000, timestamp: Date.now() }],
      pwm5: [{ value: 1000, timestamp: Date.now() }],
      pwm6: [{ value: 1000, timestamp: Date.now() }],
      pwm7: [{ value: 1000, timestamp: Date.now() }],
      pwm8: [{ value: 1000, timestamp: Date.now() }]
    },
    
    // ========== KPI历史数据（用于KPI图表显示）==========
    kpiHistory: {
      computing: [],       // 算力资源历史
      communication: [],   // 通信资源历史
      energy: [],         // 能耗指标历史
      mission: [],         // 任务效能历史
      performance: []      // 飞行性能历史
    },
    
    // ========== 数据记录信息 ==========
    dataRecording: {
      enabled: false,        // 是否启用数据记录
      recordingStartTime: null, // 记录开始时间
      recordCount: 0,        // 记录的数据包数量
      recordFilePath: '',      // 记录文件路径
      lastRecordTime: null     // 最后记录时间
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
      hostIp: '192.168.1.1',
      hostPort: 18504,
      remoteIp: '192.168.1.10',
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
      
      wsInstance = useWebSocket('ws://localhost:8000/ws/drone')
      
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
        this.addLog(`WebSocket 错误: ${error}`, 'error')
      })
      
      wsInstance.onMessage((message) => {
        console.log('[Store] WebSocket收到消息')
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
        wsInstance.close()
        wsInstance = null
      }
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
        
        console.log('[Store] 收到WebSocket消息:', data.type, data)
        
        // 处理UDP数据包装类型
        if (data.type === 'udp_data') {
          const innerType = data.data?.type || 'unknown'
          const innerData = data.data?.data || data.data || {}
          
          console.log('[Store] 解析UDP数据，内部类型:', innerType, '内部数据:', innerData)
          
          switch (innerType) {
            case 'fcs_states':
              this.updateFlightState(innerData)
              this.addLog('收到飞行状态数据', 'info')
              break
            
            case 'fcs_pwms':
              this.updateMotorPWMs(innerData)
              this.addHistoryData('pwmData', innerData)
              this.addLog(`收到PWM数据 [${Array.isArray(innerData) ? innerData.length : (innerData.pwms?.length || 0)}个通道]`, 'info')
              break
            
            case 'fcs_datactrl':
              this.updateControlLoop(innerData)
              this.addLog('收到控制循环数据', 'info')
              break
            
            case 'fcs_gncbus':
              this.updateGNCBus(innerData)
              this.addLog('收到GN&C总线数据', 'info')
              break
            
            case 'avoiflag':
              this.updateAvoiFlag(innerData)
              this.addLog('收到避障标志', 'info')
              break
              
            case 'fcs_datafutaba':
              this.updateFCSData(innerData)
              this.addLog('收到遥控数据', 'info')
              break
            
            case 'fcs_esc':
              this.updateESCData(innerData)
              this.addLog('收到电机数据', 'info')
              break
            
            case 'fcs_datagcs':
              this.updateGCSData(innerData)
              this.addLog('收到GCS数据', 'info')
              break
            
            case 'fcs_param':
              this.updateFCSParam(innerData)
              this.addLog('收到参数数据', 'info')
              break
              
            case 'lidar_obstacles':
              this.updateLidarObstacles(innerData)
              // this.addLog(`收到雷达障碍物 [${innerData.obstacle_count}个]`, 'info')
              break
            
            default:
              console.warn('[Store] 未知UDP数据类型:', innerType)
          }
          return
        }
        
        switch (data.type) {
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
          
          case 'config_update':
            this.updateConfig(data.data)
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
      console.log('[Store] 更新飞行状态:', data)
      
      // 方式1: 新格式 - 直接更新fcsStates完整结构体
      if (data.states_lat !== undefined) {
        this.fcsStates.states_lat = parseFloat(data.states_lat)
      }
      if (data.states_lon !== undefined) {
        this.fcsStates.states_lon = parseFloat(data.states_lon)
      }
      if (data.states_height !== undefined) {
        this.fcsStates.states_height = parseFloat(data.states_height)
      }
      if (data.states_Vx_GS !== undefined) {
        this.fcsStates.states_Vx_GS = parseFloat(data.states_Vx_GS)
      }
      if (data.states_Vy_GS !== undefined) {
        this.fcsStates.states_Vy_GS = parseFloat(data.states_Vy_GS)
      }
      if (data.states_Vz_GS !== undefined) {
        this.fcsStates.states_Vz_GS = parseFloat(data.states_Vz_GS)
      }
      if (data.states_p !== undefined) {
        this.fcsStates.states_p = parseFloat(data.states_p)
      }
      if (data.states_q !== undefined) {
        this.fcsStates.states_q = parseFloat(data.states_q)
      }
      if (data.states_r !== undefined) {
        this.fcsStates.states_r = parseFloat(data.states_r)
      }
      if (data.states_phi !== undefined) {
        this.fcsStates.states_phi = parseFloat(data.states_phi)
      }
      if (data.states_theta !== undefined) {
        this.fcsStates.states_theta = parseFloat(data.states_theta)
      }
      if (data.states_psi !== undefined) {
        this.fcsStates.states_psi = parseFloat(data.states_psi)
      }
      
      // 方式2: 旧格式 - 保持向后兼容
      if (data.roll !== undefined) {
        this.attitude.roll = parseFloat(data.roll)
        this.fcsStates.states_phi = parseFloat(data.roll)
      }
      if (data.pitch !== undefined) {
        this.attitude.pitch = parseFloat(data.pitch)
        this.fcsStates.states_theta = parseFloat(data.pitch)
      }
      if (data.yaw !== undefined) {
        this.attitude.yaw = parseFloat(data.yaw)
        this.fcsStates.states_psi = parseFloat(data.yaw)
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
        this.angularVelocity.p = parseFloat(data.angular_velocity_x)
        this.fcsStates.states_p = parseFloat(data.angular_velocity_x)
      }
      if (data.angular_velocity_y !== undefined) {
        this.angularVelocity.q = parseFloat(data.angular_velocity_y)
        this.fcsStates.states_q = parseFloat(data.angular_velocity_y)
      }
      if (data.angular_velocity_z !== undefined) {
        this.angularVelocity.r = parseFloat(data.angular_velocity_z)
        this.fcsStates.states_r = parseFloat(data.angular_velocity_z)
      }
      
      // 记录历史数据用于图表显示
      this.addHistoryData('flightState', data)
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
      
      // 旧格式 - 保持向后兼容
      if (data.pos_x !== undefined) this.gncBus.pos_x = parseFloat(data.pos_x)
      if (data.pos_y !== undefined) this.gncBus.pos_y = parseFloat(data.pos_y)
      if (data.pos_z !== undefined) this.gncBus.pos_z = parseFloat(data.pos_z)
      if (data.vel_x !== undefined) this.gncBus.vel_x = parseFloat(data.vel_x)
      if (data.vel_y !== undefined) this.gncBus.vel_y = parseFloat(data.vel_y)
      if (data.vel_z !== undefined) this.gncBus.vel_z = parseFloat(data.vel_z)
      if (data.euler_phi !== undefined) this.gncBus.euler_phi = parseFloat(data.euler_phi)
      if (data.euler_theta !== undefined) this.gncBus.euler_theta = parseFloat(data.euler_theta)
      if (data.euler_psi !== undefined) this.gncBus.euler_psi = parseFloat(data.euler_psi)
      if (data.control_mode !== undefined) this.gncBus.control_mode = parseInt(data.control_mode)
      if (data.flight_mode !== undefined) this.gncBus.flight_mode = parseInt(data.flight_mode)
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
      }
      if (data.Tele_GCS_Mission !== undefined) {
        this.gcsData.Tele_GCS_Mission = parseInt(data.Tele_GCS_Mission)
      }
      if (data.Tele_GCS_Val !== undefined) {
        this.gcsData.Tele_GCS_Val = parseFloat(data.Tele_GCS_Val)
      }
      if (data.Tele_GCS_com_GCS_fail !== undefined) {
        this.gcsData.Tele_GCS_com_GCS_fail = parseInt(data.Tele_GCS_com_GCS_fail)
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
     * 更新雷达状态
     */
    updateLidarStatus(data) {
      if (data.is_running !== undefined) this.lidarStatus.isRunning = !!data.is_running
      if (data.lidar_connected !== undefined) this.lidarStatus.lidarConnected = !!data.lidar_connected
      if (data.imu_data_valid !== undefined) this.lidarStatus.imuDataValid = !!data.imu_data_valid
      if (data.motion_comp_active !== undefined) this.lidarStatus.motionCompActive = !!data.motion_comp_active
    },
    
    /**
     * 更新规划系统遥测
     */
    updatePlanningTelemetry(data) {
      if (data.seq_id !== undefined) this.planningTelemetry.seqId = parseInt(data.seq_id)
      if (data.timestamp !== undefined) this.planningTelemetry.timestamp = parseInt(data.timestamp)
      if (data.current_pos_x !== undefined) this.planningTelemetry.currentPosX = parseFloat(data.current_pos_x)
      if (data.current_pos_y !== undefined) this.planningTelemetry.currentPosY = parseFloat(data.current_pos_y)
      if (data.current_pos_z !== undefined) this.planningTelemetry.currentPosZ = parseFloat(data.current_pos_z)
      if (data.current_vel !== undefined) this.planningTelemetry.currentVel = parseFloat(data.current_vel)
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
      if (data.local_traj && Array.isArray(data.local_traj)) {
        this.localTraj = data.local_traj
        console.log('[Store] 更新局部轨迹:', this.localTraj.length, '个点')
      }
    },
    
    /**
     * 更新障碍物数据
     */
    updateObstacles(data) {
      this.obstacles = data.obstacles || []
    },

    /**
     * 更新雷达感知障碍物数据 (ObstacleOutput_T)
     */
    updateLidarObstacles(data) {
      if (!data) return
      
      this.lidarObstacles = data.obstacles || []
      // 可以在这里更新其他相关状态，如时间戳等
      // console.log(`[Store] 更新雷达障碍物: ${this.lidarObstacles.length}个`)
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
        
        const response = await fetch('http://localhost:8000/api/replay/headers')
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
        
        const response = await fetch('http://localhost:8000/api/replay/chart', {
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
            const phi = data.states_phi ?? data.roll ?? this.fcsStates.states_phi
            this.history.rollActual.push({ value: phi, timestamp })
          }
          if (data.states_theta !== undefined || data.pitch !== undefined) {
            const theta = data.states_theta ?? data.pitch ?? this.fcsStates.states_theta
            this.history.pitchActual.push({ value: theta, timestamp })
          }
          if (data.states_psi !== undefined || data.yaw !== undefined) {
            const psi = data.states_psi ?? data.yaw ?? this.fcsStates.states_psi
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
        if (type === 'scan_lidar') {
           return `[范围:${params.ip_start}-${params.ip_end}]`
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
        const response = await fetch('http://localhost:8000/api/command', {
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
      this.config = { ...this.config, ...config }
    },
    
    /**
     * 更新轨迹点
     */
    addTrajectoryPoint(x, y, z) {
      const lastPoint = this.trajectory[this.trajectory.length - 1]
      
      // 距离阈值，避免记录过于密集的点
      if (lastPoint) {
        const distance = Math.sqrt(
          Math.pow(x - lastPoint.x, 2) +
          Math.pow(y - lastPoint.y, 2) +
          Math.pow(z - lastPoint.z, 2)
        )
        if (distance < 0.5) {
          return
        }
      }
      
      this.trajectory.push({
        x, y, z,
        timestamp: Date.now()
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