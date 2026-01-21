"""
LiDAR和IMU相关协议定义
基于提供的C头文件，定义Python对应的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Optional
import struct


# ================================================================
# 基本类型定义（与C/C++保持一致）
# ================================================================

# 类型别名（对应C中的typedef）
real_T = float          # double (64位)
real32_T = float        # float (32位)
int8_T = int           # signed char (8位)
int32_T = int          # int (32位)
int64_T = int          # long long (64位)
uint8_T = int          # unsigned char (8位)
uint16_T = int         # unsigned short (16位)
uint32_T = int         # unsigned int (32位)
uint64_T = int         # unsigned long long (64位)
boolean_T = bool       # 布尔型


# ================================================================
# 道通协议常量定义
# ================================================================

# LiDAR相关功能字
NCLINK_RECEIVE_LIDAR_OBSTACLES = 0x50  # 接收 ObstacleOutput_T 障碍物数组
NCLINK_RECEIVE_LIDAR_OBSTACLE_INFO = 0x51  # 接收 ObstacleInfo_T 单个障碍物信息
NCLINK_RECEIVE_LIDAR_PERF = 0x52  # 接收 PerformanceMetrics_T 性能统计
NCLINK_RECEIVE_LIDAR_STATUS = 0x53  # 接收 SystemStatus_T 系统状态
NCLINK_SEND_LIDAR_CONFIG = 0x54  # 发送 LidarObstacleConfig_T 配置

# IMU相关功能字
NCLINK_SEND_IMU_DATA = 0x60  # 发送 IMUInputData_T IMU数据


# ================================================================
# LiDAR相关数据结构体定义
# ================================================================

@dataclass
class ObstacleInfo_T:
    """
    障碍物信息结构
    对应C: ObstacleInfo_T
    """
    # 位置信息 (ENU坐标系, 单位: m)
    position_x: real32_T = 0.0  # 东向坐标 (m), 相对于起飞点
    position_y: real32_T = 0.0  # 北向坐标 (m), 相对于起飞点
    position_z: real32_T = 0.0  # 天向坐标 (m), 相对于起飞点
    
    # 尺寸信息 (单位: m)
    size_x: real32_T = 0.0  # 长度 (m), 沿东向
    size_y: real32_T = 0.0  # 宽度 (m), 沿北向
    size_z: real32_T = 0.0  # 高度 (m), 沿天向
    
    # 高度范围 (单位: m)
    height_min: real32_T = 0.0  # 最低点高度 (m)
    height_max: real32_T = 0.0  # 最高点高度 (m)
    
    # 距离与方位角
    distance: real32_T = 0.0  # 到原点的距离 (m)
    azimuth: real32_T = 0.0  # 方位角 (rad, 0=东向, 逆时针为正)
    
    # 置信度评估
    confidence: real32_T = 0.0  # 置信度 [0.0, 1.0]
    
    # 点云统计
    point_count: int32_T = 0  # 聚类包含的点数
    density: real32_T = 0.0  # 点密度 (点/立方米)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ObstacleInfo_T':
        """从字节数据解析"""
        # 总共 13个float32 + 1个int32 = 56字节
        fmt = '<fffffffffffff f'  # 13 floats + 1 int
        if len(data) < 56:
            return cls()
        
        values = struct.unpack(fmt, data[:56])
        return cls(
            position_x=values[0],
            position_y=values[1],
            position_z=values[2],
            size_x=values[3],
            size_y=values[4],
            size_z=values[5],
            height_min=values[6],
            height_max=values[7],
            distance=values[8],
            azimuth=values[9],
            confidence=values[10],
            point_count=int(values[11]),
            density=values[12]
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'position_x': float(self.position_x),
            'position_y': float(self.position_y),
            'position_z': float(self.position_z),
            'size_x': float(self.size_x),
            'size_y': float(self.size_y),
            'size_z': float(self.size_z),
            'height_min': float(self.height_min),
            'height_max': float(self.height_max),
            'distance': float(self.distance),
            'azimuth': float(self.azimuth),
            'confidence': float(self.confidence),
            'point_count': self.point_count,
            'density': float(self.density)
        }


@dataclass
class ObstacleOutput_T:
    """
    障碍物输出数组
    对应C: ObstacleOutput_T
    """
    obstacle_count: int32_T = 0  # 检测到的障碍物数量
    obstacles: List[ObstacleInfo_T] = field(default_factory=list)  # 障碍物数组
    
    # 时间戳信息
    timestamp_sec: real_T = 0.0  # 时间戳 (秒)
    timestamp_us: uint64_T = 0  # 时间戳 (微秒)
    
    # 帧信息
    frame_id: int32_T = 0  # 帧ID (递增计数)
    input_point_count: int32_T = 0  # 输入点云点数
    filtered_point_count: int32_T = 0  # 滤波后点云点数
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ObstacleOutput_T':
        """从字节数据解析"""
        # 结构: obstacle_count(4) + obstacles数组(56*N) + frame_info(8+4+4+4)
        if len(data) < 20:  # 最小长度
            return cls()
        
        offset = 0
        
        # 解析obstacle_count
        obstacle_count = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        
        # 解析时间戳
        timestamp_sec = struct.unpack('<d', data[offset:offset+8])[0]
        offset += 8
        timestamp_us = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        
        # 解析帧信息
        frame_id = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        input_point_count = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        filtered_point_count = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        
        # 解析障碍物数组
        obstacles = []
        max_obstacles = min(obstacle_count, 50)  # MAX_OBSTACLES = 50
        
        for i in range(max_obstacles):
            if offset + 56 <= len(data):
                obs = ObstacleInfo_T.from_bytes(data[offset:offset+56])
                obstacles.append(obs)
                offset += 56
        
        return cls(
            obstacle_count=obstacle_count,
            obstacles=obstacles,
            timestamp_sec=timestamp_sec,
            timestamp_us=timestamp_us,
            frame_id=frame_id,
            input_point_count=input_point_count,
            filtered_point_count=filtered_point_count
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'obstacle_count': self.obstacle_count,
            'obstacles': [obs.to_dict() for obs in self.obstacles],
            'timestamp_sec': float(self.timestamp_sec),
            'timestamp_us': self.timestamp_us,
            'frame_id': self.frame_id,
            'input_point_count': self.input_point_count,
            'filtered_point_count': self.filtered_point_count
        }


@dataclass
class PerformanceMetrics_T:
    """
    性能统计结构
    对应C: PerformanceMetrics_T
    """
    # 处理时间 (单位: ms)
    processing_time_ms: real32_T = 0.0  # 单帧处理总时间 (ms)
    frame_rate: real32_T = 0.0  # 帧率 (FPS)
    
    # 各阶段耗时 (单位: ms)
    voxel_filter_time_ms: real32_T = 0.0  # 体素滤波耗时 (ms)
    ground_segment_time_ms: real32_T = 0.0  # 地面分割耗时 (ms)
    clustering_time_ms: real32_T = 0.0  # 聚类耗时 (ms)
    motion_comp_time_ms: real32_T = 0.0  # 运动补偿耗时 (ms)
    coord_transform_time_ms: real32_T = 0.0  # 坐标转换耗时 (ms)
    
    # 点云统计
    input_points: int32_T = 0  # 输入点云点数
    filtered_points: int32_T = 0  # 滤波后点云点数
    filter_ratio: real32_T = 0.0  # 滤波比例 (%)
    
    # 障碍物统计
    obstacle_count: int32_T = 0  # 检测到的障碍物数量
    
    # 帧信息
    frame_id: int32_T = 0  # 帧ID
    timestamp_sec: real_T = 0.0  # 时间戳 (秒)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'PerformanceMetrics_T':
        """从字节数据解析"""
        # 结构: 10 floats (40B) + 4 ints (16B) + 1 double (8B) = 64字节
        fmt = '<fffffffff iiiid i'
        if len(data) < 64:
            return cls()
        
        values = struct.unpack(fmt, data[:64])
        return cls(
            processing_time_ms=values[0],
            frame_rate=values[1],
            voxel_filter_time_ms=values[2],
            ground_segment_time_ms=values[3],
            clustering_time_ms=values[4],
            motion_comp_time_ms=values[5],
            coord_transform_time_ms=values[6],
            input_points=values[7],
            filtered_points=values[8],
            filter_ratio=values[9],
            obstacle_count=values[10],
            frame_id=values[11],
            timestamp_sec=values[12]
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'processing_time_ms': float(self.processing_time_ms),
            'frame_rate': float(self.frame_rate),
            'voxel_filter_time_ms': float(self.voxel_filter_time_ms),
            'ground_segment_time_ms': float(self.ground_segment_time_ms),
            'clustering_time_ms': float(self.clustering_time_ms),
            'motion_comp_time_ms': float(self.motion_comp_time_ms),
            'coord_transform_time_ms': float(self.coord_transform_time_ms),
            'input_points': self.input_points,
            'filtered_points': self.filtered_points,
            'filter_ratio': float(self.filter_ratio),
            'obstacle_count': self.obstacle_count,
            'frame_id': self.frame_id,
            'timestamp_sec': float(self.timestamp_sec)
        }


@dataclass
class SystemStatus_T:
    """
    系统状态结构
    对应C: SystemStatus_T
    """
    is_running: boolean_T = False  # 系统运行状态
    lidar_connected: boolean_T = False  # LiDAR连接状态
    imu_data_valid: boolean_T = False  # IMU数据有效性
    motion_comp_active: boolean_T = False  # 运动补偿激活状态
    
    error_code: int32_T = 0  # 错误代码
    error_message: str = ""  # 错误消息
    
    # 统计信息
    total_frames: int32_T = 0  # 总处理帧数
    total_obstacles: int32_T = 0  # 总检测障碍物数
    avg_processing_time_ms: real32_T = 0.0  # 平均处理时间 (ms)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SystemStatus_T':
        """从字节数据解析"""
        # 结构: 4 bools (4B) + error_code (4B) + total_frames (4B) + 
        # total_obstacles (4B) + avg_time (4B) + error_msg (256B) = 276字节
        if len(data) < 20:
            return cls()
        
        offset = 0
        
        # 解析状态标志
        is_running = struct.unpack('<?', data[offset:offset+1])[0] != 0
        offset += 1
        lidar_connected = struct.unpack('<?', data[offset:offset+1])[0] != 0
        offset += 1
        imu_data_valid = struct.unpack('<?', data[offset:offset+1])[0] != 0
        offset += 1
        motion_comp_active = struct.unpack('<?', data[offset:offset+1])[0] != 0
        offset += 1
        
        # 解析错误代码
        error_code = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        
        # 解析统计信息
        total_frames = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        total_obstacles = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        avg_processing_time_ms = struct.unpack('<f', data[offset:offset+4])[0]
        offset += 4
        
        # 解析错误消息（256字节）
        error_message = data[offset:offset+256].decode('utf-8', errors='ignore').rstrip('\x00')
        
        return cls(
            is_running=is_running,
            lidar_connected=lidar_connected,
            imu_data_valid=imu_data_valid,
            motion_comp_active=motion_comp_active,
            error_code=error_code,
            error_message=error_message,
            total_frames=total_frames,
            total_obstacles=total_obstacles,
            avg_processing_time_ms=avg_processing_time_ms
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'is_running': self.is_running,
            'lidar_connected': self.lidar_connected,
            'imu_data_valid': self.imu_data_valid,
            'motion_comp_active': self.motion_comp_active,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'total_frames': self.total_frames,
            'total_obstacles': self.total_obstacles,
            'avg_processing_time_ms': float(self.avg_processing_time_ms)
        }


# ================================================================
# IMU相关数据结构体定义
# ================================================================

@dataclass
class IMUInputData_T:
    """
    IMU输入数据结构
    对应C: IMUInputData_T
    """
    # 时间信息
    timestamp_sec: real_T = 0.0  # 主时间基准 (秒)
    timestamp_us: uint64_T = 0  # 微秒级时间戳
    
    # 姿态信息 (欧拉角, 单位: rad)
    roll: real32_T = 0.0  # 横滚角 (绕X轴, Body → NED)
    pitch: real32_T = 0.0  # 俯仰角 (绕Y轴, Body → NED)
    yaw: real32_T = 0.0  # 偏航角 (绕Z轴, Body → NED)
    
    # 姿态信息 (四元数 [w,x,y,z])
    q0: real32_T = 0.0  # 四元数 w 分量
    q1: real32_T = 0.0  # 四元数 x 分量
    q2: real32_T = 0.0  # 四元数 y 分量
    q3: real32_T = 0.0  # 四元数 z 分量
    
    # 机体传感器数据 (Body Frame)
    angular_velocity_x: real32_T = 0.0  # 角速度 X轴 (rad/s)
    angular_velocity_y: real32_T = 0.0  # 角速度 Y轴 (rad/s)
    angular_velocity_z: real32_T = 0.0  # 角速度 Z轴 (rad/s)
    linear_acceleration_x: real32_T = 0.0  # 线加速度 X轴 (m/s²)
    linear_acceleration_y: real32_T = 0.0  # 线加速度 Y轴 (m/s²)
    linear_acceleration_z: real32_T = 0.0  # 线加速度 Z轴 (m/s²)
    
    # 速度信息 (机体速度, 单位: m/s)
    velocity_x: real32_T = 0.0  # 机体速度 X (m/s)
    velocity_y: real32_T = 0.0  # 机体速度 Y (m/s)
    velocity_z: real32_T = 0.0  # 机体速度 Z (m/s)
    
    # 速度信息 (NED坐标系, 单位: m/s)
    velocity_north: real32_T = 0.0  # NED速度 北向 (m/s)
    velocity_east: real32_T = 0.0  # NED速度 东向 (m/s)
    velocity_down: real32_T = 0.0  # NED速度 地向 (m/s)
    
    # 位置信息 (WGS84坐标系)
    latitude: real_T = 0.0  # 纬度 (rad, WGS84)
    longitude: real_T = 0.0  # 经度 (rad, WGS84)
    altitude: real32_T = 0.0  # 高度 (m, WGS84椭球面)
    
    # 状态信息
    ukf_status: int32_T = 0  # UKF滤波器状态 (0=未初始化, 1=收敛)
    gps_week: int32_T = 0  # GPS周数
    gps_time: real_T = 0.0  # GPS周内秒数
    is_valid: boolean_T = False  # 数据有效性标志
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'IMUInputData_T':
        """
        从字节数据解析
        结构: timestamp(8+8=16B) + euler(3*4=12B) + quaternion(4*4=16B) + 
                angular_vel(3*4=12B) + linear_accel(3*4=12B) + 
                body_vel(3*4=12B) + ned_vel(3*4=12B) + 
                position(8+8+4=20B) + status(4*4=16B) = 128字节
        """
        if len(data) < 128:
            return cls()
        
        offset = 0
        
        # 解析时间戳
        timestamp_sec = struct.unpack('<d', data[offset:offset+8])[0]
        offset += 8
        timestamp_us = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        
        # 解析欧拉角
        roll, pitch, yaw = struct.unpack('<fff', data[offset:offset+12])
        offset += 12
        
        # 解析四元数
        q0, q1, q2, q3 = struct.unpack('<ffff', data[offset:offset+16])
        offset += 16
        
        # 解析角速度
        angular_velocity_x, angular_velocity_y, angular_velocity_z = struct.unpack('<fff', data[offset:offset+12])
        offset += 12
        
        # 解析线加速度
        linear_acceleration_x, linear_acceleration_y, linear_acceleration_z = struct.unpack('<fff', data[offset:offset+12])
        offset += 12
        
        # 解析机体速度
        velocity_x, velocity_y, velocity_z = struct.unpack('<fff', data[offset:offset+12])
        offset += 12
        
        # 解析NED速度
        velocity_north, velocity_east, velocity_down = struct.unpack('<fff', data[offset:offset+12])
        offset += 12
        
        # 解析位置
        latitude = struct.unpack('<d', data[offset:offset+8])[0]
        offset += 8
        longitude = struct.unpack('<d', data[offset:offset+8])[0]
        offset += 8
        altitude = struct.unpack('<f', data[offset:offset+4])[0]
        offset += 4
        
        # 解析状态信息
        ukf_status = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        gps_week = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        gps_time = struct.unpack('<d', data[offset:offset+8])[0]
        offset += 8
        is_valid = struct.unpack('<?', data[offset:offset+1])[0] != 0
        
        return cls(
            timestamp_sec=timestamp_sec,
            timestamp_us=timestamp_us,
            roll=roll, pitch=pitch, yaw=yaw,
            q0=q0, q1=q1, q2=q2, q3=q3,
            angular_velocity_x=angular_velocity_x,
            angular_velocity_y=angular_velocity_y,
            angular_velocity_z=angular_velocity_z,
            linear_acceleration_x=linear_acceleration_x,
            linear_acceleration_y=linear_acceleration_y,
            linear_acceleration_z=linear_acceleration_z,
            velocity_x=velocity_x, velocity_y=velocity_y, velocity_z=velocity_z,
            velocity_north=velocity_north, velocity_east=velocity_east, velocity_down=velocity_down,
            latitude=latitude, longitude=longitude, altitude=altitude,
            ukf_status=ukf_status, gps_week=gps_week, gps_time=gps_time,
            is_valid=is_valid
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'timestamp_sec': float(self.timestamp_sec),
            'timestamp_us': self.timestamp_us,
            'roll': float(self.roll),
            'pitch': float(self.pitch),
            'yaw': float(self.yaw),
            'quaternion': {
                'w': float(self.q0),
                'x': float(self.q1),
                'y': float(self.q2),
                'z': float(self.q3)
            },
            'angular_velocity': {
                'x': float(self.angular_velocity_x),
                'y': float(self.angular_velocity_y),
                'z': float(self.angular_velocity_z)
            },
            'linear_acceleration': {
                'x': float(self.linear_acceleration_x),
                'y': float(self.linear_acceleration_y),
                'z': float(self.linear_acceleration_z)
            },
            'body_velocity': {
                'x': float(self.velocity_x),
                'y': float(self.velocity_y),
                'z': float(self.velocity_z)
            },
            'ned_velocity': {
                'north': float(self.velocity_north),
                'east': float(self.velocity_east),
                'down': float(self.velocity_down)
            },
            'position': {
                'latitude': float(self.latitude),
                'longitude': float(self.longitude),
                'altitude': float(self.altitude)
            },
            'ukf_status': self.ukf_status,
            'gps_week': self.gps_week,
            'gps_time': float(self.gps_time),
            'is_valid': self.is_valid
        }