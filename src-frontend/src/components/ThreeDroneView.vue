<template>
  <div class="three-drone-view" ref="container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, toRaw, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

// Refs
const container = ref(null)

// Three.js 对象
let scene, camera, renderer, controls
let droneGroup, droneBody, rotors = []
let dropLine = null
let groundShadow = null
let trajectoryLine = null  // 历史轨迹
let globalPathMesh = null    // 全局路径 Mesh (Tube)
let localTrajMesh = null    // 局部轨迹 Mesh (Tube)
let globalPathMarker = null
let localTrajMarker = null
let globalPathStartMarker = null
let globalPathGoalMarker = null
let localTrajEndMarker = null
let globalPathMaterial = null
let localTrajMaterial = null
let obstacleMeshes = []
let horizonRing = null        // 空间姿态环
let thrustPillars = []         // 推力柱数组
let historyPoints = []
let hasAutoFramed = false
const maxHistoryPoints = 500
const maxTrajectoryPoints = 500  // 轨迹最大点数
const renderDelayMs = 120
const poseBuffer = []
let animationFrameId = null
const renderedPose = {
  x: 0,
  y: 0,
  z: 0,
  pitch: 0,
  roll: 0,
  yaw: 0,
}

// 电机PWM历史值（当前协议下为0~1的归一化比值）
const motorPwmData = ref([0, 0, 0, 0, 0, 0])

const toRadians = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return 0
  }
  return THREE.MathUtils.degToRad(numeric)
}

const isFiniteNumber = (value) => Number.isFinite(Number(value))

const hasMeaningfulPoint = (point = {}) => {
  if (!point) {
    return false
  }

  return isFiniteNumber(point.x) && isFiniteNumber(point.y) && isFiniteNumber(point.z)
}

const normalizePoint = (point = {}) => {
  if (Array.isArray(point)) {
    return {
      x: Number(point[0]) || 0,
      y: Number(point[1]) || 0,
      z: Number(point[2]) || 0
    }
  }

  return {
    x: Number(point.x ?? point.pos_x ?? point.current_pos_x ?? 0) || 0,
    y: Number(point.y ?? point.pos_y ?? point.current_pos_y ?? 0) || 0,
    z: Number(point.z ?? point.pos_z ?? point.current_pos_z ?? 0) || 0
  }
}

const toThreeVector = (point = {}) => {
  const normalized = normalizePoint(point)
  return new THREE.Vector3(normalized.x, normalized.z, -normalized.y)
}

const alignedGlobalPath = computed(() => (droneStore.globalPath || []).map((point) => droneStore._alignPlanningPoint(point)))
const alignedLocalTraj = computed(() => (droneStore.localTraj || []).map((point) => droneStore._alignPlanningPoint(point)))

const scenePose = computed(() => {
  const actualPose = droneStore.actualPose || {}
  const flight = droneStore.realtimeViews?.flightState || {}
  const rawFlight = flight.raw || {}
  return {
    timestamp: Number(actualPose.timestamp ?? droneStore.realtimeViews?.updatedAt) || Date.now(),
    x: Number.isFinite(Number(actualPose.x)) ? Number(actualPose.x) : 0,
    y: Number.isFinite(Number(actualPose.y)) ? Number(actualPose.y) : 0,
    z: Number.isFinite(Number(actualPose.z)) ? Number(actualPose.z) : (Number(flight.height) || 0),
    pitch: toRadians(actualPose.pitch ?? rawFlight.states_theta ?? flight.theta ?? 0),
    roll: toRadians(actualPose.roll ?? rawFlight.states_phi ?? flight.phi ?? 0),
    yaw: toRadians(actualPose.yaw ?? rawFlight.states_psi ?? flight.psi ?? 0)
  }
})

const alignedTrajectory = computed(() => droneStore.trajectory || [])

// 当前障碍物数据源仅使用规划遥测派生结果
const activeObstacles = computed(() => {
  if (droneStore.obstacles && droneStore.obstacles.length > 0) {
    return droneStore.obstacles.map(o => ({
      ...droneStore._alignPlanningPoint({
        x: o.cx ?? o.center?.x ?? 0,
        y: o.cy ?? o.center?.y ?? 0,
        z: o.cz ?? o.center?.z ?? 0
      }),
      sx: o.sx ?? o.size?.x ?? 1.0,
      sy: o.sy ?? o.size?.y ?? 1.0,
      sz: o.sz ?? o.size?.z ?? 1.0,
      type: 'planning'
    }))
  }
  
  return []
})

// 监听电机数据
watch(() => droneStore.pwms, (newPwms) => {
  if (newPwms && newPwms.length >= 6) {
    // 获取前6个电机数据并更新
    motorPwmData.value = newPwms.slice(0, 6)
  }
}, { deep: true })

watch(scenePose, (sample) => {
  if (!sample) {
    return
  }
  const previous = poseBuffer[poseBuffer.length - 1]
  if (previous && previous.timestamp === sample.timestamp) {
    poseBuffer[poseBuffer.length - 1] = { ...sample }
  } else {
    poseBuffer.push({ ...sample })
  }
  while (poseBuffer.length > 24) {
    poseBuffer.shift()
  }
}, { deep: true, immediate: true })

// 初始化 Three.js 场景
const initScene = () => {
  const width = container.value.clientWidth
  const height = container.value.clientHeight

  // 创建场景（深邃黑色背景）
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x050508)
  scene.fog = new THREE.Fog(0x050508, 40, 200)

  // 创建相机
  camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 5000)
  camera.position.set(8, 5, 8)
  camera.lookAt(0, 0, 0)

  // 创建渲染器
  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  container.value.appendChild(renderer.domElement)

  // 创建控制器 - 启用完整的鼠标交互
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 3
  controls.maxDistance = 100
  controls.maxPolarAngle = Math.PI  // 允许360度垂直旋转
  controls.minPolarAngle = 0
  controls.enablePan = true
  controls.enableRotate = true
  controls.enableZoom = true
  controls.enableKeys = false  // 禁用键盘控制，只用鼠标

  // 添加环境光（更暗，营造深邃感）
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.3)
  scene.add(ambientLight)

  // 添加主光源（更强的主光）
  const mainLight = new THREE.DirectionalLight(0xffffff, 1.5)
  mainLight.position.set(20, 30, 20)
  mainLight.castShadow = true
  mainLight.shadow.mapSize.width = 2048
  mainLight.shadow.mapSize.height = 2048
  mainLight.shadow.camera.near = 0.5
  mainLight.shadow.camera.far = 100
  scene.add(mainLight)

  // 添加辅助光源（科技蓝）
  const fillLight = new THREE.DirectionalLight(0x3288fa, 0.3)
  fillLight.position.set(-20, 10, -20)
  scene.add(fillLight)

  // 添加地面网格（深灰色，更淡雅）
  const gridHelper = new THREE.GridHelper(200, 50, 0x2a2a2a, 0x151515)
  gridHelper.position.y = -0.01
  scene.add(gridHelper)

  // 创建无人机（六旋翼）
  createDrone()

  // 创建空间姿态环
  createHorizonRing()

  // 创建推力柱
  createThrustPillars()

  // 创建垂直投影线
  createDropLine()
  
  // 创建地面阴影
  createGroundShadow()
  
  // 创建历史轨迹（带垂直投影幕）
  createHistoryTrail()
  
  // 创建全局路径和局部轨迹
  createGlobalPath()
  createLocalTraj()
  
  // 开始动画循环
  animate()
}

// 创建六旋翼无人机模型
const createDrone = () => {
  droneGroup = new THREE.Group()

  // 无人机机身材质（更深的金属色）
  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0x1a1a1a,
    metalness: 0.8,
    roughness: 0.2
  })

  const accentMaterial = new THREE.MeshStandardMaterial({
    color: 0x3288fa,  // Apollo 蓝色
    metalness: 0.6,
    roughness: 0.3,
    emissive: 0x3288fa,
    emissiveIntensity: 0.2
  })

  const rotorMaterial = new THREE.MeshStandardMaterial({
    color: 0xdddddd,
    metalness: 0.9,
    roughness: 0.1
  })

  // 创建机身主体（六边形）
  const bodyGeometry = new THREE.CylinderGeometry(0.5, 0.6, 0.15, 6)
  droneBody = new THREE.Mesh(bodyGeometry, bodyMaterial)
  droneBody.castShadow = true
  droneBody.position.y = 0.1
  droneBody.rotation.x = Math.PI / 2
  droneGroup.add(droneBody)

  // 创建机身顶部
  const topGeometry = new THREE.CylinderGeometry(0.2, 0.15, 0.25, 16)
  const topPart = new THREE.Mesh(topGeometry, accentMaterial)
  topPart.position.y = 0.25
  droneGroup.add(topPart)

  // 六旋翼布局位置（X形布局）
  const armPositions = [
    { x: 0.7,  z: 0.4,  rotY: Math.PI / 6 },   // 前右
    { x: -0.7, z: 0.4,  rotY: Math.PI / 6 },   // 前左
    { x: 1.0,  z: -0.4, rotY: -Math.PI / 6 },  // 右侧
    { x: -1.0, z: -0.4, rotY: -Math.PI / 6 },  // 左侧
    { x: 0.4,  z: -0.8, rotY: 0 },              // 后右
    { x: -0.4, z: -0.8, rotY: 0 }               // 后左
  ]

  armPositions.forEach((pos, index) => {
    // 创建机臂
    const armGeometry = new THREE.CylinderGeometry(0.03, 0.035, 1.2, 8)
    const arm = new THREE.Mesh(armGeometry, bodyMaterial)
    
    // 计算机臂旋转角度
    const angle = Math.atan2(pos.z, pos.x)
    arm.rotation.z = Math.PI / 2
    arm.rotation.y = angle
    arm.position.set(pos.x / 2, 0.05, pos.z / 2)
    arm.castShadow = true
    droneGroup.add(arm)

    // 创建电机座
    const motorGeometry = new THREE.CylinderGeometry(0.08, 0.08, 0.15, 16)
    const motor = new THREE.Mesh(motorGeometry, accentMaterial)
    motor.position.set(pos.x, 0.1, pos.z)
    droneGroup.add(motor)

    // 创建螺旋桨
    const rotorGeometry = new THREE.CylinderGeometry(0.28, 0.28, 0.008, 32)
    const rotor = new THREE.Mesh(rotorGeometry, rotorMaterial)
    rotor.position.set(pos.x, 0.2, pos.z)
    rotor.rotation.x = Math.PI / 2
    rotor.userData = { 
      rotationSpeed: index % 2 === 0 ? 0.3 : -0.3 
    }
    rotors.push(rotor)
    droneGroup.add(rotor)

    // LED 指示灯（前两个绿色，其他红色）
    const ledGeometry = new THREE.SphereGeometry(0.025, 8, 8)
    const ledMaterial = new THREE.MeshStandardMaterial({
      color: index < 2 ? 0x4caf50 : 0xf44336,
      emissive: index < 2 ? 0x4caf50 : 0xf44336,
      emissiveIntensity: 0.8
    })
    const led = new THREE.Mesh(ledGeometry, ledMaterial)
    led.position.set(pos.x * 1.1, 0.1, pos.z * 1.1)
    droneGroup.add(led)
  })

  // 放置无人机场景中
  scene.add(droneGroup)
}

// 创建空间姿态环（人工地平线）
const createHorizonRing = () => {
  const ringGeo = new THREE.TorusGeometry(2.2, 0.03, 16, 64)
  const ringMat = new THREE.MeshBasicMaterial({ 
    color: 0x00ffff,  // 青色
    transparent: true, 
    opacity: 0.3
  })
  horizonRing = new THREE.Mesh(ringGeo, ringMat)
  horizonRing.rotation.x = Math.PI / 2  // 躺平
  scene.add(horizonRing)

  // 添加十字标记
  const markGeo = new THREE.BufferGeometry()
  const markPoints = [
    new THREE.Vector3(-2.4, 0, 0),
    new THREE.Vector3(2.4, 0, 0),
    new THREE.Vector3(0, 0, -2.4),
    new THREE.Vector3(0, 0, 2.4)
  ]
  markGeo.setFromPoints(markPoints)
  const markMat = new THREE.LineBasicMaterial({
    color: 0x00ffff,
    transparent: true,
    opacity: 0.3
  })
  const marks = new THREE.Line(markGeo, markMat)
  marks.rotation.x = Math.PI / 2
  scene.add(marks)
}

// 创建推力柱（旋翼转速可视化）
const createThrustPillars = () => {
  const positions = [
    { x: 0.7,  z: 0.4 },
    { x: -0.7, z: 0.4 },
    { x: 1.0,  z: -0.4 },
    { x: -1.0, z: -0.4 },
    { x: 0.4,  z: -0.8 },
    { x: -0.4, z: -0.8 }
  ]

  positions.forEach((pos, index) => {
    const geometry = new THREE.CylinderGeometry(0.1, 0.1, 1, 32)
    geometry.translate(0, -0.5, 0)  // 锚点在顶部，向下延伸
    
    const material = new THREE.MeshBasicMaterial({
      color: 0x00ff00,
      transparent: true,
      opacity: 0.4
    })
    
    const pillar = new THREE.Mesh(geometry, material)
    pillar.position.set(pos.x, 0, pos.z)
    droneGroup.add(pillar)
    thrustPillars.push(pillar)
  })
}

// 更新推力柱可视化
const updateThrustPillars = () => {
  const pwmData = motorPwmData.value
  
  // 确保有6个柱子
  if (thrustPillars.length < 6) return;

  for (let i = 0; i < 6; i++) {
    const pwm = Number(pwmData[i]) || 0;
    const pillar = thrustPillars[i];
    
    // 当前实机协议直接给出0.0~1.0附近的推力比值
    const ratio = Math.max(0, Math.min(1, pwm))
    
    // 2. 调整长度
    const scale = Math.max(0.1, ratio * 3)  // 最长3米
    pillar.scale.set(1, scale, 1)
    
    // 3. 调整颜色（蓝 -> 绿 -> 红）
    const color = new THREE.Color()
    if (ratio < 0.33) {
      // 低转速：蓝->绿
      color.lerpColors(new THREE.Color(0x2196f3), new THREE.Color(0x4caf50), ratio * 3)
    } else if (ratio < 0.66) {
      // 中转速：绿->黄
      color.lerpColors(new THREE.Color(0x4caf50), new THREE.Color(0xffeb3b), (ratio - 0.33) * 3)
    } else {
      // 高转速：黄->红
      color.lerpColors(new THREE.Color(0xffeb3b), new THREE.Color(0xf44336), (ratio - 0.66) * 3)
    }
    
    pillar.material.color = color
    pillar.material.opacity = 0.3 + ratio * 0.3
  }
}

// 创建垂直投影线
const createDropLine = () => {
  const material = new THREE.LineDashedMaterial({ 
    color: 0x00bcd4,
    dashSize: 0.5,
    gapSize: 0.3,
    transparent: true,
    opacity: 0.5
  })

  const geometry = new THREE.BufferGeometry()
  const points = [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, 0, 0)
  ]
  geometry.setFromPoints(points)

  dropLine = new THREE.Line(geometry, material)
  dropLine.computeLineDistances()
  scene.add(dropLine)
}

// 创建地面阴影
const createGroundShadow = () => {
  const geometry = new THREE.CircleGeometry(1.0, 32)
  const material = new THREE.MeshBasicMaterial({
    color: 0x000000,
    transparent: true,
    opacity: 0.3
  })
  groundShadow = new THREE.Mesh(geometry, material)
  groundShadow.rotation.x = -Math.PI / 2
  groundShadow.position.y = -0.01
  scene.add(groundShadow)
}

// 创建历史轨迹（简单的暗红色细线）
const createHistoryTrail = () => {
  const positions = new Float32Array(maxHistoryPoints * 3)
  const colors = new Float32Array(maxHistoryPoints * 3)
  
  const histGeometry = new THREE.BufferGeometry()
  histGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  histGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  
  const histMaterial = new THREE.LineBasicMaterial({
    vertexColors: true,
    linewidth: 1,
    transparent: true,
    opacity: 0.6
  })
  
  trajectoryLine = new THREE.Line(histGeometry, histMaterial)
  trajectoryLine.frustumCulled = false
  scene.add(trajectoryLine)

  updateHistoryTrail()
}

// 创建全局路径轨迹 (初始化材质)
const createGlobalPath = () => {
  globalPathMaterial = new THREE.MeshStandardMaterial({
    color: 0x3288fa,
    emissive: 0x3288fa,
    emissiveIntensity: 0.5,
    roughness: 0.4,
    metalness: 0.6
  })
}

// 创建局部轨迹轨迹 (初始化材质)
const createLocalTraj = () => {
  localTrajMaterial = new THREE.MeshStandardMaterial({
    color: 0x4caf50,
    emissive: 0x4caf50,
    emissiveIntensity: 0.5,
    roughness: 0.4,
    metalness: 0.6
  })
}

const hydrateSceneFromStore = () => {
  updateGlobalPath(alignedGlobalPath.value)
  updateLocalTraj(alignedLocalTraj.value)
  updateObstacleVisualization(activeObstacles.value)
  updateHistoryTrail()
  frameTelemetryScene()
}

const buildPathVectors = (pathPoints) => {
  const rawPoints = toRaw(pathPoints || [])
  const vectors = []
  const count = Math.min(rawPoints.length, maxTrajectoryPoints)

  for (let i = 0; i < count; i++) {
    const point = normalizePoint(toRaw(rawPoints[i]))

    if (!hasMeaningfulPoint(point)) {
      continue
    }

    vectors.push(toThreeVector(point))
  }

  return vectors
}

const createTextSprite = (text, accentColor = '#ffffff') => {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 96
  const context = canvas.getContext('2d')

  if (!context) {
    return null
  }

  context.clearRect(0, 0, canvas.width, canvas.height)
  context.fillStyle = 'rgba(5, 10, 18, 0.86)'
  context.strokeStyle = accentColor
  context.lineWidth = 4
  context.beginPath()
  context.roundRect(8, 8, canvas.width - 16, canvas.height - 16, 18)
  context.fill()
  context.stroke()
  context.fillStyle = accentColor
  context.font = '700 34px Segoe UI'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillText(text, canvas.width / 2, canvas.height / 2)

  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false
  })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(3.6, 1.35, 1)
  return sprite
}

const createLabeledPathMarker = (vector, markerColor, radius, label, labelColor) => {
  const group = new THREE.Group()
  const sphere = createPathMarker(new THREE.Vector3(0, 0, 0), markerColor, radius)
  const ringGeometry = new THREE.TorusGeometry(radius * 1.2, Math.max(radius * 0.08, 0.04), 12, 48)
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: markerColor,
    transparent: true,
    opacity: 0.75,
    depthWrite: false
  })
  const ring = new THREE.Mesh(ringGeometry, ringMaterial)
  ring.rotation.x = Math.PI / 2
  group.add(sphere)
  group.add(ring)

  const labelSprite = createTextSprite(label, labelColor || `#${markerColor.toString(16).padStart(6, '0')}`)
  if (labelSprite) {
    labelSprite.position.set(0, radius * 2.1, 0)
    group.add(labelSprite)
  }

  group.position.copy(vector)
  group.renderOrder = 12
  return group
}

const disposeObject3D = (object) => {
  if (!object) {
    return
  }

  object.traverse((child) => {
    if (child.geometry) {
      child.geometry.dispose()
    }
    if (child.material) {
      const materials = Array.isArray(child.material) ? child.material : [child.material]
      materials.forEach((material) => {
        if (material.map) {
          material.map.dispose()
        }
        material.dispose()
      })
    }
  })
}

const clearSceneObject = (objectRef) => {
  if (!scene || !objectRef) {
    return null
  }

  scene.remove(objectRef)
  disposeObject3D(objectRef)
  return null
}

const frameTelemetryScene = () => {
  if (!scene || !camera || !controls || hasAutoFramed) {
    return
  }

  const points = []
  buildPathVectors(alignedGlobalPath.value).forEach((point) => points.push(point))
  buildPathVectors(alignedLocalTraj.value).forEach((point) => points.push(point))
  alignedTrajectory.value.slice(-maxHistoryPoints).forEach((point) => points.push(toThreeVector(point)))
  activeObstacles.value.forEach((obstacle) => points.push(toThreeVector(obstacle)))
  if (droneGroup) {
    points.push(droneGroup.position.clone())
  }

  if (points.length < 2) {
    return
  }

  const bounds = new THREE.Box3()
  points.forEach((point) => bounds.expandByPoint(point))
  const center = new THREE.Vector3()
  const size = new THREE.Vector3()
  bounds.getCenter(center)
  bounds.getSize(size)
  const radius = Math.max(size.length() * 0.5, 18)

  controls.target.copy(center)
  camera.position.set(center.x + radius * 0.72, center.y + radius * 0.46, center.z + radius * 0.72)
  camera.lookAt(center)
  controls.update()
  hasAutoFramed = true
}

const resetAutoFrameIfSceneEmpty = () => {
  const hasGlobalPath = Array.isArray(droneStore.globalPath) && droneStore.globalPath.length > 0
  const hasLocalTraj = Array.isArray(droneStore.localTraj) && droneStore.localTraj.length > 0
  const hasTrajectory = Array.isArray(alignedTrajectory.value) && alignedTrajectory.value.length > 0
  const hasObstacles = Array.isArray(activeObstacles.value) && activeObstacles.value.length > 0

  if (!hasGlobalPath && !hasLocalTraj && !hasTrajectory && !hasObstacles) {
    hasAutoFramed = false
  }
}

const createPathMarker = (vector, color, radius) => {
  const geometry = new THREE.SphereGeometry(radius, 24, 24)
  const material = new THREE.MeshPhongMaterial({
    color,
    emissive: color,
    emissiveIntensity: 0.35,
    transparent: true,
    opacity: 0.95,
    depthWrite: false
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.copy(vector)
  return mesh
}

const clearGlobalPath = () => {
  globalPathMesh = clearSceneObject(globalPathMesh)
}

const clearGlobalPathMarker = () => {
  globalPathMarker = clearSceneObject(globalPathMarker)
}

const clearGlobalPathAnchors = () => {
  globalPathStartMarker = clearSceneObject(globalPathStartMarker)
  globalPathGoalMarker = clearSceneObject(globalPathGoalMarker)
}

const clearLocalTraj = () => {
  localTrajMesh = clearSceneObject(localTrajMesh)
}

const clearLocalTrajMarker = () => {
  localTrajMarker = clearSceneObject(localTrajMarker)
}

const clearLocalTrajAnchors = () => {
  localTrajEndMarker = clearSceneObject(localTrajEndMarker)
}

// 更新全局路径 (TubeGeometry)
const updateGlobalPath = (pathPoints) => {
  if (!scene) return; 
  if (!pathPoints || pathPoints.length === 0) {
    clearGlobalPath()
    clearGlobalPathMarker()
    clearGlobalPathAnchors()
    resetAutoFrameIfSceneEmpty()
    return
  }
  
  const vectors = buildPathVectors(pathPoints)
  
  if (vectors.length < 2) {
      clearGlobalPath()
      clearGlobalPathMarker()
      clearGlobalPathAnchors()
      if (vectors.length === 1) {
        globalPathMarker = createPathMarker(vectors[0], 0x3288fa, 0.75)
        globalPathMarker.renderOrder = 8
        scene.add(globalPathMarker)
      }
      resetAutoFrameIfSceneEmpty()
      return;
  }

  clearGlobalPathMarker()
  clearGlobalPathAnchors()

  // 1. 清理旧模型
  clearGlobalPath()

  // 2. 创建曲线
  const curve = new THREE.CatmullRomCurve3(vectors) 

  // 3. 创建管道几何体
  const tubeGeometry = new THREE.TubeGeometry(curve, Math.max(4, vectors.length * 4), 0.62, 10, false)
  
  // 4. 材质设置
  const material = new THREE.MeshPhongMaterial({
    color: 0x3288fa,
    emissive: 0x0f4c81,
    specular: 0xffffff,
    shininess: 24,
    transparent: true,
    opacity: 0.42,
    side: THREE.DoubleSide,
    depthWrite: false
  })
  
  globalPathMesh = new THREE.Mesh(tubeGeometry, material)
  globalPathMesh.castShadow = false
  globalPathMesh.renderOrder = 4
  scene.add(globalPathMesh)

  globalPathStartMarker = createLabeledPathMarker(vectors[0], 0x35d07f, 0.55, 'START', '#7fffd4')
  globalPathGoalMarker = createLabeledPathMarker(vectors[vectors.length - 1], 0xffb020, 0.68, 'GOAL', '#ffd166')
  scene.add(globalPathStartMarker)
  scene.add(globalPathGoalMarker)
  frameTelemetryScene()
}

// 更新局部轨迹 (TubeGeometry)
const updateLocalTraj = (trajPoints) => {
  if (!scene) return;
  if (!trajPoints || trajPoints.length === 0) {
    clearLocalTraj()
    clearLocalTrajMarker()
    clearLocalTrajAnchors()
    resetAutoFrameIfSceneEmpty()
    return
  }
  
  const vectors = buildPathVectors(trajPoints)
  
  if (vectors.length < 2) {
    clearLocalTraj()
    clearLocalTrajMarker()
    clearLocalTrajAnchors()
    if (vectors.length === 1) {
      localTrajMarker = createPathMarker(vectors[0], 0x4caf50, 0.42)
      localTrajMarker.renderOrder = 10
      scene.add(localTrajMarker)
    }
    resetAutoFrameIfSceneEmpty()
    return
  }

  clearLocalTrajMarker()
  clearLocalTrajAnchors()

  // 1. 清理旧模型
  clearLocalTraj()

  const curve = new THREE.CatmullRomCurve3(vectors)
  const tubeGeometry = new THREE.TubeGeometry(curve, Math.max(4, vectors.length * 4), 0.24, 10, false)
  
  const material = new THREE.MeshPhongMaterial({
    color: 0x4caf50,
    emissive: 0x0d5f2a,
    transparent: true,
    opacity: 0.96,
    side: THREE.DoubleSide,
    depthWrite: false
  })
  
  localTrajMesh = new THREE.Mesh(tubeGeometry, material)
  localTrajMesh.castShadow = true
  localTrajMesh.renderOrder = 6
  scene.add(localTrajMesh)

  localTrajEndMarker = createLabeledPathMarker(vectors[vectors.length - 1], 0x4caf50, 0.32, 'LOCAL', '#7CFC8D')
  scene.add(localTrajEndMarker)
  frameTelemetryScene()
}

// 更新障碍物可视化
const updateObstacleVisualization = (obstacles) => {
  if (!scene) return
  
  // 1. 清理旧障碍物
  obstacleMeshes.forEach(mesh => {
    scene.remove(mesh)
    disposeObject3D(mesh)
  })
  obstacleMeshes = []

  if (!obstacles || obstacles.length === 0) {
    resetAutoFrameIfSceneEmpty()
    return
  }
  
  const rawObstacles = toRaw(obstacles)
  
  rawObstacles.forEach(obs => {
     // 统一后的格式: x, y, z, sx, sy, sz
     const px = Number(obs.x) || 0;
     const py = Number(obs.y) || 0;
     const pz = Number(obs.z) || 0;
     
     const sx = Number(obs.sx) || 1.0;
     const sy = Number(obs.sy) || 1.0;
     const sz = Number(obs.sz) || 1.0;
     
     const group = new THREE.Group()
     const geometry = new THREE.BoxGeometry(Math.max(sx, 0.35), Math.max(sz, 0.35), Math.max(sy, 0.35))
     const material = new THREE.MeshStandardMaterial({
       color: 0xff4fd8,
       transparent: true,
       opacity: 0.24,
       roughness: 0.35,
       metalness: 0.1
     })
     const mesh = new THREE.Mesh(geometry, material)
     const edges = new THREE.LineSegments(
       new THREE.EdgesGeometry(geometry),
       new THREE.LineBasicMaterial({ color: 0xff9ae8, transparent: true, opacity: 0.9 })
     )
     const footprint = new THREE.Mesh(
       new THREE.RingGeometry(Math.max(Math.min(sx, sy) * 0.22, 0.2), Math.max(Math.max(sx, sy) * 0.52, 0.35), 24),
       new THREE.MeshBasicMaterial({ color: 0xff9ae8, transparent: true, opacity: 0.28, side: THREE.DoubleSide })
     )
     footprint.rotation.x = -Math.PI / 2
     footprint.position.y = -Math.max(sz, 0.35) / 2 + 0.02

     group.add(mesh)
     group.add(edges)
     group.add(footprint)
     group.position.set(px, pz, -py)
     group.renderOrder = 9

     scene.add(group)
     obstacleMeshes.push(group)
  });

  frameTelemetryScene()
}

// 更新历史轨迹
const updateHistoryTrail = () => {
  if (!trajectoryLine) return
  
  const positions = trajectoryLine.geometry.attributes.position.array
  const colors = trajectoryLine.geometry.attributes.color.array
  
  for (let i = 0; i < historyPoints.length; i++) {
    const point = historyPoints[i]
    const idx = i * 3
    
    positions[idx] = point.x
    positions[idx + 1] = point.y
    positions[idx + 2] = point.z
    
    const alpha = 0.3 + (i / historyPoints.length) * 0.7
    const color = new THREE.Color().setHSL(0.02, 0.8, 0.5)
    
    colors[idx] = color.r * alpha
    colors[idx + 1] = color.g * alpha
    colors[idx + 2] = color.b * alpha
  }
  
  trajectoryLine.geometry.setDrawRange(0, historyPoints.length)
  trajectoryLine.geometry.attributes.position.needsUpdate = true
  trajectoryLine.geometry.attributes.color.needsUpdate = true
}


// 更新垂直投影线
const updateDropLine = () => {
  if (!dropLine || !droneGroup) return
  
  const droneHeight = droneGroup.position.y
  const points = [
    new THREE.Vector3(0, droneHeight, 0),
    new THREE.Vector3(0, 0, 0)
  ]
  
  dropLine.geometry.setFromPoints(points)
  dropLine.computeLineDistances()

  if (groundShadow) {
    groundShadow.position.set(
      droneGroup.position.x,
      -0.01,
      droneGroup.position.z
    )
    const scale = Math.max(0.5, 1 - droneHeight * 0.05)
    groundShadow.scale.set(scale, scale, scale)
  }
}

// 更新无人机姿态
const updateDroneAttitude = () => {
  if (droneGroup) {
    const pitch = renderedPose.pitch
    const roll = renderedPose.roll
    const yaw = renderedPose.yaw

    const euler = new THREE.Euler(pitch, yaw, roll, 'XYZ')
    droneGroup.setRotationFromEuler(euler)
    
    droneGroup.position.x = renderedPose.x
    droneGroup.position.y = Math.max(0, renderedPose.z)
    droneGroup.position.z = -renderedPose.y
    
    // 更新投影线
    updateDropLine()
    
    // 更新空间姿态环
    if (horizonRing) {
      horizonRing.position.copy(droneGroup.position)
      // 环保持水平，只跟随航向
      horizonRing.rotation.y = -yaw
    }

    if (controls) {
      controls.target.lerp(droneGroup.position, 0.05)
    }
  }
}

const updateRenderPose = () => {
  if (!poseBuffer.length) {
    return
  }

  const targetTime = Date.now() - renderDelayMs
  let currentSample = poseBuffer[0]
  let nextSample = null

  for (let index = 0; index < poseBuffer.length; index += 1) {
    if (poseBuffer[index].timestamp <= targetTime) {
      currentSample = poseBuffer[index]
      nextSample = poseBuffer[index + 1] || null
    } else {
      nextSample = poseBuffer[index]
      break
    }
  }

  if (!nextSample || nextSample.timestamp <= currentSample.timestamp) {
    Object.assign(renderedPose, currentSample)
  } else {
    const alpha = Math.min(1, Math.max(0, (targetTime - currentSample.timestamp) / (nextSample.timestamp - currentSample.timestamp)))
    renderedPose.x = THREE.MathUtils.lerp(currentSample.x, nextSample.x, alpha)
    renderedPose.y = THREE.MathUtils.lerp(currentSample.y, nextSample.y, alpha)
    renderedPose.z = THREE.MathUtils.lerp(currentSample.z, nextSample.z, alpha)
    renderedPose.pitch = THREE.MathUtils.lerp(currentSample.pitch, nextSample.pitch, alpha)
    renderedPose.roll = THREE.MathUtils.lerp(currentSample.roll, nextSample.roll, alpha)
    renderedPose.yaw = THREE.MathUtils.lerp(currentSample.yaw, nextSample.yaw, alpha)
  }

  while (poseBuffer.length > 2 && poseBuffer[1].timestamp <= targetTime) {
    poseBuffer.shift()
  }
}

// 动画循环
const animate = () => {
  animationFrameId = requestAnimationFrame(animate)

  // 旋转螺旋桨
  rotors.forEach(rotor => {
    rotor.rotation.z += rotor.userData.rotationSpeed
  })

  // 更新推力柱
  updateThrustPillars()

  // 更新控制器
  controls.update()

  // 更新延迟平滑后的渲染姿态
  updateRenderPose()

  // 更新无人机姿态
  updateDroneAttitude()

  // 渲染场景
  renderer.render(scene, camera)
}

// 处理窗口大小变化
const onWindowResize = () => {
  if (container.value && camera && renderer) {
    const width = container.value.clientWidth
    const height = container.value.clientHeight
    
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    renderer.setSize(width, height)
  }
}

// 监听全局路径数据
watch(alignedGlobalPath, (newPath) => {
  updateGlobalPath(newPath)
}, { deep: true, immediate: true })

// 监听局部轨迹数据
watch(alignedLocalTraj, (newTraj) => {
  updateLocalTraj(newTraj)
}, { deep: true, immediate: true })

watch(alignedTrajectory, (newTrajectory) => {
  historyPoints = (newTrajectory || []).slice(-maxHistoryPoints).map(point => ({
    x: Number(point.x) || 0,
    y: Number(point.z) || 0,
    z: -(Number(point.y) || 0)
  }))
  updateHistoryTrail()
  resetAutoFrameIfSceneEmpty()
}, { deep: true, immediate: true })

// 监听规划遥测派生的障碍物数据
watch(activeObstacles, (newObstacles) => {
  updateObstacleVisualization(newObstacles)
}, { deep: true, immediate: true })

// 使用 ResizeObserver 响应容器尺寸变化（分隔线拖拽、面板切换等）
let resizeObserver = null

// 生命周期钩子
onMounted(() => {
  initScene()
  hydrateSceneFromStore()
  window.addEventListener('resize', onWindowResize)

  if (container.value) {
    resizeObserver = new ResizeObserver(() => {
      onWindowResize()
    })
    resizeObserver.observe(container.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  
  if (renderer) {
    renderer.dispose()
    container.value?.removeChild(renderer.domElement)
  }
  
  if (controls) {
    controls.dispose()
  }
  
  if (scene) {
    scene.traverse((object) => {
      if (object.geometry) {
        object.geometry.dispose()
      }
      if (object.material) {
        if (Array.isArray(object.material)) {
          object.material.forEach(material => material.dispose())
        } else {
          object.material.dispose()
        }
      }
    })
  }
  
  // 清理轨迹线
  if (trajectoryLine) {
    trajectoryLine.geometry.dispose()
    trajectoryLine.material.dispose()
  }

  if (globalPathMarker) {
    disposeObject3D(globalPathMarker)
  }

  if (globalPathStartMarker) {
    disposeObject3D(globalPathStartMarker)
  }

  if (globalPathGoalMarker) {
    disposeObject3D(globalPathGoalMarker)
  }

  if (localTrajMarker) {
    disposeObject3D(localTrajMarker)
  }

  if (localTrajEndMarker) {
    disposeObject3D(localTrajEndMarker)
  }
  
  // 清理障碍物
  obstacleMeshes.forEach(mesh => {
      disposeObject3D(mesh)
  })
})
</script>

<style scoped>
.three-drone-view {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #050508;
}

/* 信息开关 */
.info-toggle {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 100;
}

.toggle-btn {
  width: 40px;
  height: 40px;
  background: rgba(15, 15, 20, 0.9);
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #888;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-btn:hover {
  background: rgba(50, 136, 250, 0.2);
  border-color: #3288fa;
  color: #fff;
}

.toggle-btn.active {
  background: rgba(50, 136, 250, 0.3);
  border-color: #3288fa;
  color: #3288fa;
}

/* 场景信息面板 */
.scene-info {
  position: absolute;
  top: 80px;
  right: 20px;
  background: rgba(15, 15, 20, 0.9);
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 16px;
  min-width: 160px;
  backdrop-filter: blur(10px);
  z-index: 90;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #2a2a2a;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  color: #666;
  font-size: 12px;
  font-weight: 500;
}

.info-item .value {
  color: #3288fa;
  font-size: 14px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}
</style>