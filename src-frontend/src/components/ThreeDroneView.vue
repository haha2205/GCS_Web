<template>
  <div class="three-drone-view" ref="container">
    <!-- 视图控制模式切换 -->
    <div class="view-controls">
      <button
        v-for="viewMode in viewModes"
        :key="viewMode.id"
        class="view-mode-btn"
        :class="{ active: currentViewMode === viewMode.id }"
        @click="switchViewMode(viewMode.id)"
        :title="viewMode.name"
      >
        {{ viewMode.icon }}
      </button>
    </div>

    <!-- 信息显示开关 -->
    <div class="info-toggle">
      <button 
        class="toggle-btn" 
        @click="showInfo = !showInfo"
        :class="{ active: showInfo }"
      >
        {{ showInfo ? '📊' : '📉' }}
      </button>
    </div>

    <!-- 场景信息面板（可隐藏） -->
    <div v-if="showInfo" class="scene-info">
      <div class="info-item">
        <span class="label">高度</span>
        <span class="value">{{ (droneStore.fcsStates?.altitude ?? 0).toFixed(1) }}m</span>
      </div>
      <div class="info-item">
        <span class="label">俯仰</span>
        <span class="value">{{ formatAngle(props.pitch) }}°</span>
      </div>
      <div class="info-item">
        <span class="label">横滚</span>
        <span class="value">{{ formatAngle(props.roll) }}°</span>
      </div>
      <div class="info-item">
        <span class="label">航向</span>
        <span class="value">{{ formatAngle(props.yaw) }}°</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

// Props
const props = defineProps({
  pitch: {
    type: Number,
    default: 0
  },
  roll: {
    type: Number,
    default: 0
  },
  yaw: {
    type: Number,
    default: 0
  }
})

// Refs
const container = ref(null)
const currentViewMode = ref('chase')
const showInfo = ref(false)

// 视图模式定义
const viewModes = [
  { id: 'chase', name: '跟随模式', icon: '✈️' },
  { id: 'topdown', name: '上帝视角', icon: '📷' },
  { id: 'fpv', name: '第一人称', icon: '👁️' }
]

// Three.js 对象
let scene, camera, renderer, controls
let droneGroup, droneBody, rotors = []
let dropLine = null
let groundShadow = null
let trajectoryLine = null
let horizonRing = null        // 空间姿态环
let thrustPillars = []         // 推力柱数组
let historyPoints = []
const maxHistoryPoints = 500

const sceneData = ref({
  pitch: props.pitch,
  roll: props.roll,
  yaw: props.yaw
})

// 模拟电机PWM数据（1000-2000）
const motorPwmData = ref([1100, 1150, 1200, 1180, 1120, 1160])

// 格式化角度显示
const formatAngle = (angle) => {
  return (angle * 180 / Math.PI).toFixed(1)
}

// 切换视图模式
const switchViewMode = (mode) => {
  currentViewMode.value = mode
  
  if (!camera || !controls) return

  switch (mode) {
    case 'chase':
      const altitude = droneStore.fcsStates?.altitude ?? 0
      const offset = new THREE.Vector3(-10, 5, 10)
      camera.position.copy(droneGroup.position.clone().add(offset))
      controls.target.copy(droneGroup.position)
      break
      
    case 'topdown':
      controls.target.set(0, 0, 0)
      camera.position.set(0, 60, 0)
      camera.lookAt(0, 0, 0)
      break
      
    case 'fpv':
      const forward = new THREE.Vector3(0, 2, 15)
      forward.applyEuler(droneGroup.rotation)
      camera.position.copy(droneGroup.position.clone().add(forward))
      controls.target.copy(droneGroup.position.clone().add(forward))
      break
  }
}

// 初始化 Three.js 场景
const initScene = () => {
  const width = container.value.clientWidth
  const height = container.value.clientHeight

  // 创建场景（深邃黑色背景）
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x050508)
  scene.fog = new THREE.Fog(0x050508, 40, 200)

  // 创建相机
  camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 500)
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
  
  pwmData.forEach((pwm, index) => {
    if (!thrustPillars[index]) return
    
    // 1. 归一化 (0.0 ~ 1.0)
    const ratio = Math.max(0, Math.min(1, (pwm - 1000) / 1000))
    
    // 2. 调整长度
    const scale = Math.max(0.1, ratio * 3)  // 最长3米
    thrustPillars[index].scale.set(1, scale, 1)
    
    // 3. 调整颜色（蓝 -> 绿 -> 红）
    const color = new THREE.Color()
    if (ratio < 0.33) {
      color.lerpColors(new THREE.Color(0x2196f3), new THREE.Color(0x4caf50), ratio * 3)
    } else if (ratio < 0.66) {
      color.lerpColors(new THREE.Color(0x4caf50), new THREE.Color(0xffeb3b), (ratio - 0.33) * 3)
    } else {
      color.lerpColors(new THREE.Color(0xffeb3b), new THREE.Color(0xf44336), (ratio - 0.66) * 3)
    }
    
    thrustPillars[index].material.color = color
    thrustPillars[index].material.opacity = 0.3 + ratio * 0.3
  })
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
  
  // 预填充历史轨迹点
  for (let i = 0; i < maxHistoryPoints; i++) {
    const t = i / maxHistoryPoints * Math.PI * 4
    historyPoints.push({
      x: Math.sin(t) * 15,
      y: 5 + Math.sin(t * Math.PI * 2) * 3,
      z: Math.cos(t) * 15
    })
  }
  
  updateHistoryTrail()
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
    const euler = new THREE.Euler(props.pitch, props.yaw, props.roll, 'XYZ')
    droneGroup.setRotationFromEuler(euler)
    
    const altitude = droneStore.fcsStates?.altitude ?? 0
    droneGroup.position.y = Math.max(0, altitude)
    
    // 更新投影线
    updateDropLine()
    
    // 更新空间姿态环
    if (horizonRing) {
      horizonRing.position.copy(droneGroup.position)
      // 环保持水平，只跟随航向
      horizonRing.rotation.y = -props.yaw
    }
    
    // 自动跟随模式下，只更新controls.target，不强制相机位置
    // 这样鼠标交互仍然有效
    if (currentViewMode.value === 'chase') {
      // 只更新目标点，让OrbitControls处理相机位置
      controls.target.lerp(droneGroup.position, 0.05)
    }
    else if (currentViewMode.value === 'fpv') {
      // FPV模式：更新相机位置到无人机前方
      const forward = new THREE.Vector3(0, 1, 8)
      forward.applyEuler(droneGroup.rotation)
      const targetPos = droneGroup.position.clone().add(forward)
      camera.position.lerp(targetPos, 0.1)
      controls.target.lerp(droneGroup.position.clone().add(new THREE.Vector3(0, 1, 5)), 0.1)
    }
  }
}

// 动画循环
const animate = () => {
  requestAnimationFrame(animate)

  // 旋转螺旋桨
  rotors.forEach(rotor => {
    rotor.rotation.z += rotor.userData.rotationSpeed
  })

  // 更新推力柱
  updateThrustPillars()

  // 更新控制器
  controls.update()

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

// 监听 props 变化
watch(() => props.pitch, (newVal) => {
  sceneData.value.pitch = newVal
})

watch(() => props.roll, (newVal) => {
  sceneData.value.roll = newVal
})

watch(() => props.yaw, (newVal) => {
  sceneData.value.yaw = newVal
})

// 生命周期钩子
onMounted(() => {
  initScene()
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  
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

/* 视图控制按钮 */
.view-controls {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 12px;
  z-index: 100;
  background: rgba(15, 15, 20, 0.9);
  padding: 10px 20px;
  border-radius: 8px;
  border: 1px solid #2a2a2a;
  backdrop-filter: blur(10px);
}

.view-mode-btn {
  width: 40px;
  height: 40px;
  background: rgba(50, 136, 250, 0.15);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 6px;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.view-mode-btn:hover {
  background: rgba(50, 136, 250, 0.3);
  transform: scale(1.1);
}

.view-mode-btn.active {
  background: rgba(50, 136, 250, 0.4);
  border-color: #3288fa;
  box-shadow: 0 0 10px rgba(50, 136, 250, 0.4);
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