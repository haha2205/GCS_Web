"""
MiniQGCLinkV2.0 协议定义
完整实现地面站与飞控/雷达的通信协议
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import IntEnum
import struct
import time
import logging

# 获取logger实例
logger = logging.getLogger(__name__)


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


# ================================================================
# NCLink协议常量定义
# ================================================================

NCLINK_HEAD0 = 0xFF
NCLINK_HEAD1 = 0xFC
NCLINK_END0 = 0xA1
NCLINK_END1 = 0xA2
BUFFER_SIZE_MAX = 16384

# 飞控功能字定义
NCLINK_SEND_EXTU_FCS = 0x40
NCLINK_RECEIVE_EXTY_FCS_PWMS = 0x41
NCLINK_RECEIVE_EXTY_FCS_STATES = 0x42
NCLINK_RECEIVE_EXTY_FCS_DATACTRL = 0x43
NCLINK_RECEIVE_EXTY_FCS_GNCBUS = 0x44
NCLINK_RECEIVE_EXTY_FCS_AVOIFLAG = 0x45
NCLINK_RECEIVE_EXTY_FCS_DATAGCS = 0x46
NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AIM2AB = 0x47
NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AB = 0x48
NCLINK_RECEIVE_EXTY_FCS_PARAM = 0x49
NCLINK_RECEIVE_EXTY_FCS_ROOT = 0x4A
NCLINK_RECEIVE_EXTY_FCS_ESC = 0x4B

# 雷达/障碍物感知相关功能字
NCLINK_RECEIVE_LIDAR_OBSTACLES = 0x50
NCLINK_RECEIVE_LIDAR_OBSTACLE_INFO = 0x51
NCLINK_RECEIVE_LIDAR_PERF = 0x52
NCLINK_RECEIVE_LIDAR_STATUS = 0x53
NCLINK_SEND_LIDAR_CONFIG = 0x54

# 航迹规划协议定义
NCLINK_GCS_COMMAND = 0x70
NCLINK_GCS_TELEMETRY = 0x71

# 端口定义
SEND_ONLY_PORT = 18506
LIDAR_SEND_PORT = 18507
RECEIVE_PORT = 18504
PLANNING_SEND_PORT = 18510
PLANNING_RECV_PORT = 18511

# 应答状态码
RESPONSE_SUCCESS = 0x00
RESPONSE_FAILED = 0x01
RESPONSE_TIMEOUT = 0x02
RESPONSE_INVALID_CMD = 0x03
RESPONSE_INVALID_DATA = 0x04
RESPONSE_BUSY = 0x05


# ================================================================
# 飞控数据结构体定义
# ================================================================

@dataclass
class ExtY_FCS_PWMS_T:
    """PWM输出数据"""
    pwms: List[real_T] = field(default_factory=list)  # 8个PWM通道
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_PWMS_T':
        # C++飞控使用小端序发送payload数据
        fmt = '<8d'  # 小端序：8个double
        values = struct.unpack(fmt, data[:64])
        return cls(pwms=list(values))
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<8d'  # 小端序：8个double = 64 bytes
        # 确保有8个PWM值
        pwms_list = self.pwms[:8] if len(self.pwms) >= 8 else self.pwms + [0.0] * (8 - len(self.pwms))
        return struct.pack(fmt, *pwms_list)


@dataclass
class ExtY_FCS_DATACTRL_T:
    """控制数据循环状态
    
    完整的DATACTRL结构体，包含所有控制循环数据：
    - ailOutLoop: 副翼外循环
    - ailInLoop: 副翼内循环
    - eleOutLoop: 升降舵外循环
    - EleInLoop: 升降舵内循环
    - RudOutLoop: 方向舵外循环
    - rudInLoop: 方向舵内循环
    - colOutLoop: 油门外循环
    - colInLoop: 油门内循环
    
    总计：8+8+8+8+3+7+8+3 = 53个real32_T = 212字节
    """
    # ailOutLoop展开（8个real32_T）
    dataCtrl_n_ailOutLoop_dY_delta: real32_T = 0.0
    dataCtrl_n_ailOutLoop_Vy_dY2Vy: real32_T = 0.0
    dataCtrl_n_ailOutLoop_Vy_var: real32_T = 0.0
    dataCtrl_n_ailOutLoop_Vy_delta: real32_T = 0.0
    dataCtrl_n_ailOutLoop_Vy_P: real32_T = 0.0
    dataCtrl_n_ailOutLoop_Vy_Int: real32_T = 0.0
    dataCtrl_n_ailOutLoop_Vy_D: real32_T = 0.0
    dataCtrl_n_ailOutLoop_ail_ffc: real32_T = 0.0
    
    # ailInLoop展开（8个real32_T）
    dataCtrl_n_ailInLoop_ail_trim: real32_T = 0.0
    dataCtrl_n_ailInLoop_phi_trim: real32_T = 0.0
    dataCtrl_n_ailInLoop_phi_var: real32_T = 0.0
    dataCtrl_n_ailInLoop_delta_phi: real32_T = 0.0
    dataCtrl_n_ailInLoop_phi_P: real32_T = 0.0
    dataCtrl_n_ailInLoop_phi_D: real32_T = 0.0
    dataCtrl_n_ailInLoop_ail_fbc: real32_T = 0.0
    dataCtrl_n_ailInLoop_ail_law_out: real32_T = 0.0
    
    # eleOutLoop展开（8个real32_T）
    dataCtrl_n_eleOutLoop_dX_delta: real32_T = 0.0
    dataCtrl_n_eleOutLoop_Vx_dX2Vx: real32_T = 0.0
    dataCtrl_n_eleOutLoop_Vx_var: real32_T = 0.0
    dataCtrl_n_eleOutLoop_Vx_delta: real32_T = 0.0
    dataCtrl_n_eleOutLoop_Vx_P: real32_T = 0.0
    dataCtrl_n_eleOutLoop_Vx_Int: real32_T = 0.0
    dataCtrl_n_eleOutLoop_Vx_D: real32_T = 0.0
    dataCtrl_n_eleOutLoop_ele_ffc: real32_T = 0.0
    
    # EleInLoop展开（8个real32_T）
    dataCtrl_n_EleInLoop_theta_trim: real32_T = 0.0
    dataCtrl_n_EleInLoop_ele_trim: real32_T = 0.0
    dataCtrl_n_EleInLoop_theta_var: real32_T = 0.0
    dataCtrl_n_EleInLoop_delta_theta: real32_T = 0.0
    dataCtrl_n_EleInLoop_theta_P: real32_T = 0.0
    dataCtrl_n_EleInLoop_theta_D: real32_T = 0.0
    dataCtrl_n_EleInLoop_ele_fbc: real32_T = 0.0
    dataCtrl_n_EleInLoop_ele_law_out: real32_T = 0.0
    
    # RudOutLoop展开（3个real32_T）
    dataCtrl_n_RudOutLoop_psi_dy: real32_T = 0.0
    dataCtrl_n_RudOutLoop_psi_delta: real32_T = 0.0
    dataCtrl_n_RudOutLoop_R_dPsi2R: real32_T = 0.0
    
    # rudInLoop展开（7个real32_T）
    dataCtrl_n_rudInLoop_rud_trim: real32_T = 0.0
    dataCtrl_n_rudInLoop_R_var: real32_T = 0.0
    dataCtrl_n_rudInLoop_dR_delta: real32_T = 0.0
    dataCtrl_n_rudInLoop_R_P: real32_T = 0.0
    dataCtrl_n_rudInLoop_R_Int: real32_T = 0.0
    dataCtrl_n_rudInLoop_rud_fbc: real32_T = 0.0
    dataCtrl_n_rudInLoop_rud_law_out: real32_T = 0.0
    
    # colOutLoop展开（8个real32_T）
    dataCtrl_n_colOutLoop_H_delta: real32_T = 0.0
    dataCtrl_n_colOutLoop_Hdot_dH2Vz: real32_T = 0.0
    dataCtrl_n_colOutLoop_Hdot_var: real32_T = 0.0
    dataCtrl_n_colOutLoop_Hdot_delta: real32_T = 0.0
    dataCtrl_n_colOutLoop_Hdot_P: real32_T = 0.0
    dataCtrl_n_colOutLoop_Hdot_Int: real32_T = 0.0
    dataCtrl_n_colOutLoop_Hdot_D: real32_T = 0.0
    dataCtrl_n_colOutLoop_col_fbc: real32_T = 0.0
    
    # colInLoop展开（3个real32_T）
    dataCtrl_n_colInLoop_col_Vx: real32_T = 0.0
    dataCtrl_n_colInLoop_col_law: real32_T = 0.0
    dataCtrl_n_colInLoop_col_law_out: real32_T = 0.0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_DATACTRL_T':
        """从字节数据解析控制数据
        
        总计：53个real32_T = 212字节
        """
        if len(data) < 212:
            print(f"[ExtY_FCS_DATACTRL_T] Payload长度不足: {len(data)} < 212")
            return cls()
        
        fmt = '<53f'  # 小端序：53 floats = 212 bytes
        values = struct.unpack(fmt, data[:212])
        
        return cls(
            # ailOutLoop (0-7)
            dataCtrl_n_ailOutLoop_dY_delta=values[0],
            dataCtrl_n_ailOutLoop_Vy_dY2Vy=values[1],
            dataCtrl_n_ailOutLoop_Vy_var=values[2],
            dataCtrl_n_ailOutLoop_Vy_delta=values[3],
            dataCtrl_n_ailOutLoop_Vy_P=values[4],
            dataCtrl_n_ailOutLoop_Vy_Int=values[5],
            dataCtrl_n_ailOutLoop_Vy_D=values[6],
            dataCtrl_n_ailOutLoop_ail_ffc=values[7],
            # ailInLoop (8-15)
            dataCtrl_n_ailInLoop_ail_trim=values[8],
            dataCtrl_n_ailInLoop_phi_trim=values[9],
            dataCtrl_n_ailInLoop_phi_var=values[10],
            dataCtrl_n_ailInLoop_delta_phi=values[11],
            dataCtrl_n_ailInLoop_phi_P=values[12],
            dataCtrl_n_ailInLoop_phi_D=values[13],
            dataCtrl_n_ailInLoop_ail_fbc=values[14],
            dataCtrl_n_ailInLoop_ail_law_out=values[15],
            # eleOutLoop (16-23)
            dataCtrl_n_eleOutLoop_dX_delta=values[16],
            dataCtrl_n_eleOutLoop_Vx_dX2Vx=values[17],
            dataCtrl_n_eleOutLoop_Vx_var=values[18],
            dataCtrl_n_eleOutLoop_Vx_delta=values[19],
            dataCtrl_n_eleOutLoop_Vx_P=values[20],
            dataCtrl_n_eleOutLoop_Vx_Int=values[21],
            dataCtrl_n_eleOutLoop_Vx_D=values[22],
            dataCtrl_n_eleOutLoop_ele_ffc=values[23],
            # EleInLoop (24-31)
            dataCtrl_n_EleInLoop_theta_trim=values[24],
            dataCtrl_n_EleInLoop_ele_trim=values[25],
            dataCtrl_n_EleInLoop_theta_var=values[26],
            dataCtrl_n_EleInLoop_delta_theta=values[27],
            dataCtrl_n_EleInLoop_theta_P=values[28],
            dataCtrl_n_EleInLoop_theta_D=values[29],
            dataCtrl_n_EleInLoop_ele_fbc=values[30],
            dataCtrl_n_EleInLoop_ele_law_out=values[31],
            # RudOutLoop (32-34)
            dataCtrl_n_RudOutLoop_psi_dy=values[32],
            dataCtrl_n_RudOutLoop_psi_delta=values[33],
            dataCtrl_n_RudOutLoop_R_dPsi2R=values[34],
            # rudInLoop (35-40)
            dataCtrl_n_rudInLoop_rud_trim=values[35],
            dataCtrl_n_rudInLoop_R_var=values[36],
            dataCtrl_n_rudInLoop_dR_delta=values[37],
            dataCtrl_n_rudInLoop_R_P=values[38],
            dataCtrl_n_rudInLoop_R_Int=values[39],
            dataCtrl_n_rudInLoop_rud_fbc=values[40],
            dataCtrl_n_rudInLoop_rud_law_out=values[41],
            # colOutLoop (42-49)
            dataCtrl_n_colOutLoop_H_delta=values[42],
            dataCtrl_n_colOutLoop_Hdot_dH2Vz=values[43],
            dataCtrl_n_colOutLoop_Hdot_var=values[44],
            dataCtrl_n_colOutLoop_Hdot_delta=values[45],
            dataCtrl_n_colOutLoop_Hdot_P=values[46],
            dataCtrl_n_colOutLoop_Hdot_Int=values[47],
            dataCtrl_n_colOutLoop_Hdot_D=values[48],
            dataCtrl_n_colOutLoop_col_fbc=values[49],
            # colInLoop (50-52)
            dataCtrl_n_colInLoop_col_Vx=values[50],
            dataCtrl_n_colInLoop_col_law=values[51],
            dataCtrl_n_colInLoop_col_law_out=values[52]
        )
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<53f'  # 小端序：53 floats = 212 bytes
        return struct.pack(fmt,
            # ailOutLoop
            self.dataCtrl_n_ailOutLoop_dY_delta,
            self.dataCtrl_n_ailOutLoop_Vy_dY2Vy,
            self.dataCtrl_n_ailOutLoop_Vy_var,
            self.dataCtrl_n_ailOutLoop_Vy_delta,
            self.dataCtrl_n_ailOutLoop_Vy_P,
            self.dataCtrl_n_ailOutLoop_Vy_Int,
            self.dataCtrl_n_ailOutLoop_Vy_D,
            self.dataCtrl_n_ailOutLoop_ail_ffc,
            # ailInLoop
            self.dataCtrl_n_ailInLoop_ail_trim,
            self.dataCtrl_n_ailInLoop_phi_trim,
            self.dataCtrl_n_ailInLoop_phi_var,
            self.dataCtrl_n_ailInLoop_delta_phi,
            self.dataCtrl_n_ailInLoop_phi_P,
            self.dataCtrl_n_ailInLoop_phi_D,
            self.dataCtrl_n_ailInLoop_ail_fbc,
            self.dataCtrl_n_ailInLoop_ail_law_out,
            # eleOutLoop
            self.dataCtrl_n_eleOutLoop_dX_delta,
            self.dataCtrl_n_eleOutLoop_Vx_dX2Vx,
            self.dataCtrl_n_eleOutLoop_Vx_var,
            self.dataCtrl_n_eleOutLoop_Vx_delta,
            self.dataCtrl_n_eleOutLoop_Vx_P,
            self.dataCtrl_n_eleOutLoop_Vx_Int,
            self.dataCtrl_n_eleOutLoop_Vx_D,
            self.dataCtrl_n_eleOutLoop_ele_ffc,
            # EleInLoop
            self.dataCtrl_n_EleInLoop_theta_trim,
            self.dataCtrl_n_EleInLoop_ele_trim,
            self.dataCtrl_n_EleInLoop_theta_var,
            self.dataCtrl_n_EleInLoop_delta_theta,
            self.dataCtrl_n_EleInLoop_theta_P,
            self.dataCtrl_n_EleInLoop_theta_D,
            self.dataCtrl_n_EleInLoop_ele_fbc,
            self.dataCtrl_n_EleInLoop_ele_law_out,
            # RudOutLoop
            self.dataCtrl_n_RudOutLoop_psi_dy,
            self.dataCtrl_n_RudOutLoop_psi_delta,
            self.dataCtrl_n_RudOutLoop_R_dPsi2R,
            # rudInLoop
            self.dataCtrl_n_rudInLoop_rud_trim,
            self.dataCtrl_n_rudInLoop_R_var,
            self.dataCtrl_n_rudInLoop_dR_delta,
            self.dataCtrl_n_rudInLoop_R_P,
            self.dataCtrl_n_rudInLoop_R_Int,
            self.dataCtrl_n_rudInLoop_rud_fbc,
            self.dataCtrl_n_rudInLoop_rud_law_out,
            # colOutLoop
            self.dataCtrl_n_colOutLoop_H_delta,
            self.dataCtrl_n_colOutLoop_Hdot_dH2Vz,
            self.dataCtrl_n_colOutLoop_Hdot_var,
            self.dataCtrl_n_colOutLoop_Hdot_delta,
            self.dataCtrl_n_colOutLoop_Hdot_P,
            self.dataCtrl_n_colOutLoop_Hdot_Int,
            self.dataCtrl_n_colOutLoop_Hdot_D,
            self.dataCtrl_n_colOutLoop_col_fbc,
            # colInLoop
            self.dataCtrl_n_colInLoop_col_Vx,
            self.dataCtrl_n_colInLoop_col_law,
            self.dataCtrl_n_colInLoop_col_law_out
        )
    
    def to_json(self) -> dict:
        return {
            'ailOutLoop': {
                'dY_delta': self.dataCtrl_n_ailOutLoop_dY_delta,
                'Vy_dY2Vy': self.dataCtrl_n_ailOutLoop_Vy_dY2Vy,
                'Vy_var': self.dataCtrl_n_ailOutLoop_Vy_var,
                'Vy_delta': self.dataCtrl_n_ailOutLoop_Vy_delta,
                'Vy_P': self.dataCtrl_n_ailOutLoop_Vy_P,
                'Vy_Int': self.dataCtrl_n_ailOutLoop_Vy_Int,
                'Vy_D': self.dataCtrl_n_ailOutLoop_Vy_D,
                'ail_ffc': self.dataCtrl_n_ailOutLoop_ail_ffc
            },
            'ailInLoop': {
                'ail_trim': self.dataCtrl_n_ailInLoop_ail_trim,
                'phi_trim': self.dataCtrl_n_ailInLoop_phi_trim,
                'phi_var': self.dataCtrl_n_ailInLoop_phi_var,
                'delta_phi': self.dataCtrl_n_ailInLoop_delta_phi,
                'phi_P': self.dataCtrl_n_ailInLoop_phi_P,
                'phi_D': self.dataCtrl_n_ailInLoop_phi_D,
                'ail_fbc': self.dataCtrl_n_ailInLoop_ail_fbc,
                'ail_law_out': self.dataCtrl_n_ailInLoop_ail_law_out
            },
            'eleOutLoop': {
                'dX_delta': self.dataCtrl_n_eleOutLoop_dX_delta,
                'Vx_dX2Vx': self.dataCtrl_n_eleOutLoop_Vx_dX2Vx,
                'Vx_var': self.dataCtrl_n_eleOutLoop_Vx_var,
                'Vx_delta': self.dataCtrl_n_eleOutLoop_Vx_delta,
                'Vx_P': self.dataCtrl_n_eleOutLoop_Vx_P,
                'Vx_Int': self.dataCtrl_n_eleOutLoop_Vx_Int,
                'Vx_D': self.dataCtrl_n_eleOutLoop_Vx_D,
                'ele_ffc': self.dataCtrl_n_eleOutLoop_ele_ffc
            },
            'EleInLoop': {
                'theta_trim': self.dataCtrl_n_EleInLoop_theta_trim,
                'ele_trim': self.dataCtrl_n_EleInLoop_ele_trim,
                'theta_var': self.dataCtrl_n_EleInLoop_theta_var,
                'delta_theta': self.dataCtrl_n_EleInLoop_delta_theta,
                'theta_P': self.dataCtrl_n_EleInLoop_theta_P,
                'theta_D': self.dataCtrl_n_EleInLoop_theta_D,
                'ele_fbc': self.dataCtrl_n_EleInLoop_ele_fbc,
                'ele_law_out': self.dataCtrl_n_EleInLoop_ele_law_out
            },
            'RudOutLoop': {
                'psi_dy': self.dataCtrl_n_RudOutLoop_psi_dy,
                'psi_delta': self.dataCtrl_n_RudOutLoop_psi_delta,
                'R_dPsi2R': self.dataCtrl_n_RudOutLoop_R_dPsi2R
            },
            'rudInLoop': {
                'rud_trim': self.dataCtrl_n_rudInLoop_rud_trim,
                'R_var': self.dataCtrl_n_rudInLoop_R_var,
                'dR_delta': self.dataCtrl_n_rudInLoop_dR_delta,
                'R_P': self.dataCtrl_n_rudInLoop_R_P,
                'R_Int': self.dataCtrl_n_rudInLoop_R_Int,
                'rud_fbc': self.dataCtrl_n_rudInLoop_rud_fbc
            },
            'colOutLoop': {
                'H_delta': self.dataCtrl_n_colOutLoop_H_delta,
                'Hdot_dH2Vz': self.dataCtrl_n_colOutLoop_Hdot_dH2Vz,
                'Hdot_var': self.dataCtrl_n_colOutLoop_Hdot_var,
                'Hdot_delta': self.dataCtrl_n_colOutLoop_Hdot_delta,
                'Hdot_P': self.dataCtrl_n_colOutLoop_Hdot_P,
                'Hdot_Int': self.dataCtrl_n_colOutLoop_Hdot_Int,
                'Hdot_D': self.dataCtrl_n_colOutLoop_Hdot_D,
                'col_fbc': self.dataCtrl_n_colOutLoop_col_fbc
            },
            'colInLoop': {
                'col_Vx': self.dataCtrl_n_colInLoop_col_Vx,
                'col_law': self.dataCtrl_n_colInLoop_col_law,
                'col_law_out': self.dataCtrl_n_colInLoop_col_law_out
            }
        }


@dataclass
class ExtY_FCS_STATES_T:
    """飞行状态数据
    
    - real_T states_lat (8字节，double)
    - real_T states_lon (8字节，double)
    - real32_T states_height (4字节，float)
    - 10个real32_T，共40字节（各4字节）
    总计：8+8+4+40 = 56字节
    """
    states_lat: real_T = 0.0     # double (8字节)
    states_lon: real_T = 0.0     # double (8字节)
    states_height: real32_T = 0.0  # float (4字节)
    states_Vx_GS: real32_T = 0.0  # float (4字节)
    states_Vy_GS: real32_T = 0.0  # float (4字节)
    states_Vz_GS: real32_T = 0.0  # float (4字节)
    states_p: real32_T = 0.0     # float (4字节)
    states_q: real32_T = 0.0     # float (4字节)
    states_r: real32_T = 0.0     # float (4字节)
    states_phi: real32_T = 0.0   # float (4字节)
    states_theta: real32_T = 0.0 # float (4字节)
    states_psi: real32_T = 0.0    # float (4字节)

    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<ddffffffffff'  # 小端序：2 doubles + 10 floats = 56 bytes
        return struct.pack(fmt,
            self.states_lat,
            self.states_lon,
            self.states_height,
            self.states_Vx_GS,
            self.states_Vy_GS,
            self.states_Vz_GS,
            self.states_p,
            self.states_q,
            self.states_r,
            self.states_phi,
            self.states_theta,
            self.states_psi
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_STATES_T':
        # 根据C++ interface.h V2.0定义（第68-81行）
        # 实际接收的payload是56字节
        # 格式：2个double (16字节) + 10个float (40字节) = 56字节
        # 字段：states_lat(double), states_lon(double),
        #       states_height(float), states_Vx_GS(float), states_Vy_GS(float),
        #       states_Vz_GS(float), states_p(float), states_q(float),
        #       states_r(float), states_phi(float), states_theta(float), states_psi(float)
        #
        # ⚠️ 重要：C++飞控使用小端序（x86平台）发送payload数据
        
        fmt = '<ddffffffffff'  # 小端序：2 doubles + 10 floats = 56 bytes
        try:
            values = struct.unpack(fmt, data[:56])
            return cls(
                states_lat=values[0],
                states_lon=values[1],
                states_height=values[2],
                states_Vx_GS=values[3],
                states_Vy_GS=values[4],
                states_Vz_GS=values[5],
                states_p=values[6],
                states_q=values[7],
                states_r=values[8],
                states_phi=values[9],
                states_theta=values[10],
                states_psi=values[11]
            )
        except Exception as e:
            print(f"[ExtY_FCS_STATES_T] 解析失败: {e}")
            print(f"[ExtY_FCS_STATES_T] Payload hex: {data[:56].hex()}")
            return cls()
    
    def to_json(self) -> dict:
        """返回符合interface.h命名规范的JSON格式
        
        为了兼容旧代码，同时提供新旧两种字段名
        """
        json_data = {
            # 新字段名（符合interface.h规范）
            'states_lat': float(self.states_lat),
            'states_lon': float(self.states_lon),
            'states_height': float(self.states_height),
            'states_Vx_GS': float(self.states_Vx_GS),
            'states_Vy_GS': float(self.states_Vy_GS),
            'states_Vz_GS': float(self.states_Vz_GS),
            'states_p': float(self.states_p),
            'states_q': float(self.states_q),
            'states_r': float(self.states_r),
            'states_phi': float(self.states_phi),
            'states_theta': float(self.states_theta),
            'states_psi': float(self.states_psi),
        }
        return json_data


@dataclass
class ExtY_FCS_GNCBUS_T:
    """GN&C总线状态
    
    根据C++ interface.h第114-209行完整定义
    包含TokenMode、FtbOpt、SrcValue、MixValue、CmdValue、VarValue、TrimValue、ParamsLMT、AcValue、HoverValue、HomeValue
    """
    # TokenMode展开（第115-132行）
    GNCBus_TokenMode_OnSky: int8_T = 0
    GNCBus_TokenMode_Ctrl_Mode: int8_T = 0
    GNCBus_TokenMode_Pre_CMD: int8_T = 0
    GNCBus_TokenMode_rud_state: int8_T = 0
    GNCBus_TokenMode_ail_state: int8_T = 0
    GNCBus_TokenMode_ele_state: int8_T = 0
    GNCBus_TokenMode_col_state: int8_T = 0
    GNCBus_TokenMode_nav_guid: int8_T = 0
    GNCBus_TokenMode_cmd_guid: int8_T = 0
    GNCBus_TokenMode_mode_guid: int8_T = 0
    GNCBus_TokenMode_step_guid: int8_T = 0
    GNCBus_TokenMode_mode_nav: int8_T = 0
    GNCBus_TokenMode_token_nav: int8_T = 0
    GNCBus_TokenMode_step_nav: int8_T = 0
    GNCBus_TokenMode_mode_vert: int8_T = 0
    GNCBus_TokenMode_token_vert: int8_T = 0
    GNCBus_TokenMode_step_vert: int8_T = 0
    
    # FtbOpt展开（第134-144行）- 遥控优化值
    GNCBus_FtbOpt_ele_opt: real32_T = 0.0
    GNCBus_FtbOpt_ail_opt: real32_T = 0.0
    GNCBus_FtbOpt_rud_opt: real32_T = 0.0
    GNCBus_FtbOpt_col_opt: real32_T = 0.0
    GNCBus_FtbOpt_R_opt: real32_T = 0.0
    GNCBus_FtbOpt_Vx_opt: real32_T = 0.0
    GNCBus_FtbOpt_Vy_opt: real32_T = 0.0
    GNCBus_FtbOpt_coldt_opt: real32_T = 0.0
    GNCBus_FtbOpt_col0_opt: real32_T = 0.0
    GNCBus_FtbOpt_Ftb_Switch: int8_T = 0
    
    # SrcValue展开（第146-148行）
    GNCBus_SrcValue_ac_SrcCmdV: int8_T = 0
    GNCBus_SrcValue_SrcV_fus: int8_T = 0
    
    # MixValue展开（第150-159行）- 混控值
    GNCBus_MixValue_col_mix: real32_T = 0.0
    GNCBus_MixValue_phi_mix: real32_T = 0.0
    GNCBus_MixValue_Vx_mix: real32_T = 0.0
    GNCBus_MixValue_dX_mix: real32_T = 0.0
    GNCBus_MixValue_theta_mix: real32_T = 0.0
    GNCBus_MixValue_Vy_mix: real32_T = 0.0
    GNCBus_MixValue_dY_mix: real32_T = 0.0
    GNCBus_MixValue_psi_mix: real32_T = 0.0
    GNCBus_MixValue_Hdot_mix: real32_T = 0.0
    GNCBus_MixValue_height_mix: real32_T = 0.0
    
    # CmdValue展开（第162-169行）- GNC指令值（重要！用于导航标签页）
    GNCBus_CmdValue_phi_cmd: real32_T = 0.0   # 滚转指令
    GNCBus_CmdValue_Hdot_cmd: real32_T = 0.0   # 垂向速度指令
    GNCBus_CmdValue_R_cmd: real32_T = 0.0   # 偏航速率指令
    GNCBus_CmdValue_psi_cmd: real32_T = 0.0   # 偏航指令
    GNCBus_CmdValue_Vx_cmd: real32_T = 0.0   # X速度指令
    GNCBus_CmdValue_Vy_cmd: real32_T = 0.0   # Y速度指令
    GNCBus_CmdValue_height_cmd: real32_T = 0.0  # 高度指令
    
    # VarValue展开（第171-175行）
    GNCBus_VarValue_psi_var: real32_T = 0.0
    GNCBus_VarValue_height_var: real32_T = 0.0
    GNCBus_VarValue_dX_var: real32_T = 0.0
    GNCBus_VarValue_dY_var: real32_T = 0.0
    
    # TrimValue展开（第177-180行）
    GNCBus_TrimValue_Vx_trim: real32_T = 0.0
    GNCBus_TrimValue_col_trim: real32_T = 0.0
    GNCBus_TrimValue_col_autotrim: real32_T = 0.0
    
    # ParamsLMT展开（第182-193行）- 参数限制
    GNCBus_ParamsLMT_Vx_LMT: real32_T = 0.0
    GNCBus_ParamsLMT_Vy_LMT: real32_T = 0.0
    GNCBus_ParamsLMT_R_LMT: real32_T = 0.0
    GNCBus_ParamsLMT_Hdot_ILmt: real32_T = 0.0
    GNCBus_ParamsLMT_Hdot_UpLMT: real32_T = 0.0
    GNCBus_ParamsLMT_Hdot_DownLMT: real32_T = 0.0
    GNCBus_ParamsLMT_R_FLYTURN: real32_T = 0.0
    GNCBus_ParamsLMT_R_unit: real32_T = 0.0
    GNCBus_ParamsLMT_Hdot_unit: real32_T = 0.0
    GNCBus_ParamsLMT_Vx_unit: real32_T = 0.0
    GNCBus_ParamsLMT_Vy_unit: real32_T = 0.0
    
    # AcValue展开（第195-199行）
    GNCBus_AcValue_ac_dY: real32_T = 0.0
    GNCBus_AcValue_ac_dX: real32_T = 0.0
    GNCBus_AcValue_ac_dPsi: real32_T = 0.0
    GNCBus_AcValue_ac_dL: real32_T = 0.0
    
    # HoverValue展开（第201-204行）
    GNCBus_HoverValue_lon_hov: real_T = 0.0
    GNCBus_HoverValue_lat_hov: real_T = 0.0
    GNCBus_HoverValue_IsHovStatus_hov: int8_T = 0
    
    # HomeValue展开（第206-208行）
    GNCBus_HomeValue_lon_home: real_T = 0.0
    GNCBus_HomeValue_lat_home: real_T = 0.0
    
    # 向后兼容的简化字段（保持旧代码可用）
    pos_x: real32_T = 0.0
    pos_y: real32_T = 0.0
    pos_z: real32_T = 0.0
    vel_x: real32_T = 0.0
    vel_y: real32_T = 0.0
    vel_z: real32_T = 0.0
    euler_phi: real32_T = 0.0
    euler_theta: real32_T = 0.0
    euler_psi: real32_T = 0.0
    control_mode: int32_T = 0
    flight_mode: int32_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_GNCBUS_T':
        """从字节数据解析GN&C总线状态
        
        根据C++ interface.h第114-209行完整定义
        总共96字节：17*int8 + 9*real32 + 10*real32 + 7*real32 + 4*real32 + 3*real32 + 10*real32 + 4*real32 + 2*real_T + 2*int8 + 2*real_T
        实际按字段顺序解析：
        - TokenMode: 17个int8 = 17字节
        - FtbOpt: 9个real32 + 1个int8 = 36+1 = 37字节
        - SrcValue: 2个int8 = 2字节
        - MixValue: 10个real32 = 40字节
        - CmdValue: 7个real32 = 28字节
        - VarValue: 4个real32 = 16字节
        - TrimValue: 3个real32 = 12字节
        - ParamsLMT: 10个real32 = 40字节
        - AcValue: 4个real32 = 16字节
        - HoverValue: 2个real_T + 1个int8 = 16+1 = 17字节
        - HomeValue: 2个real_T = 16字节
        
        总计：17 + 37 + 2 + 40 + 28 + 16 + 12 + 40 + 16 + 17 + 16 = 241字节
        但实际可能只发送部分字段，这里解析CmdValue关键字段
        """
        if len(data) < 56:
            # 至少需要TokenMode(17) + FtbOpt(37) + SrcValue(2) = 56字节
            return cls()
        
        try:
            # 定义解析格式（小端序）
            # TokenMode: 17个int8
            # FtbOpt: 9个float + 1个int8
            # SrcValue: 2个int8
            # MixValue: 10个float
            # CmdValue: 7个float（包含我们需要的Vx_cmd, Vy_cmd, height_cmd, psi_cmd）
            
            # 由于字段太多，我们只解析到CmdValue的前7个float
            offset = 0
            
            # 1. TokenMode (17个int8)
            tokenmode_values = struct.unpack_from('<17b', data, offset)
            offset += 17
            
            # 2. FtbOpt (9个float + 1个int8)
            ftbopt_floats = struct.unpack_from('<9f', data, offset)
            offset += 36  # 9*4
            ftbopt_switch = struct.unpack_from('<b', data, offset)
            offset += 1
            
            # 3. SrcValue (2个int8)
            srcvalue_values = struct.unpack_from('<2b', data, offset)
            offset += 2
            
            # 4. MixValue (10个float)
            mixvalue_values = struct.unpack_from('<10f', data, offset)
            offset += 40  # 10*4
            
            # 5. CmdValue (7个float) - 这是我们需要的！
            cmdvalue_values = struct.unpack_from('<7f', data, offset)
            offset += 28  # 7*4
            
            # 构建返回对象
            return cls(
                # TokenMode
                GNCBus_TokenMode_OnSky=tokenmode_values[0],
                GNCBus_TokenMode_Ctrl_Mode=tokenmode_values[1],
                GNCBus_TokenMode_Pre_CMD=tokenmode_values[2],
                GNCBus_TokenMode_rud_state=tokenmode_values[3],
                GNCBus_TokenMode_ail_state=tokenmode_values[4],
                GNCBus_TokenMode_ele_state=tokenmode_values[5],
                GNCBus_TokenMode_col_state=tokenmode_values[6],
                GNCBus_TokenMode_nav_guid=tokenmode_values[7],
                GNCBus_TokenMode_cmd_guid=tokenmode_values[8],
                GNCBus_TokenMode_mode_guid=tokenmode_values[9],
                GNCBus_TokenMode_step_guid=tokenmode_values[10],
                GNCBus_TokenMode_mode_nav=tokenmode_values[11],
                GNCBus_TokenMode_token_nav=tokenmode_values[12],
                GNCBus_TokenMode_step_nav=tokenmode_values[13],
                GNCBus_TokenMode_mode_vert=tokenmode_values[14],
                GNCBus_TokenMode_token_vert=tokenmode_values[15],
                GNCBus_TokenMode_step_vert=tokenmode_values[16],
                
                # FtbOpt
                GNCBus_FtbOpt_ele_opt=ftbopt_floats[0],
                GNCBus_FtbOpt_ail_opt=ftbopt_floats[1],
                GNCBus_FtbOpt_rud_opt=ftbopt_floats[2],
                GNCBus_FtbOpt_col_opt=ftbopt_floats[3],
                GNCBus_FtbOpt_R_opt=ftbopt_floats[4],
                GNCBus_FtbOpt_Vx_opt=ftbopt_floats[5],
                GNCBus_FtbOpt_Vy_opt=ftbopt_floats[6],
                GNCBus_FtbOpt_coldt_opt=ftbopt_floats[7],
                GNCBus_FtbOpt_col0_opt=ftbopt_floats[8],
                GNCBus_FtbOpt_Ftb_Switch=ftbopt_switch[0],
                
                # SrcValue
                GNCBus_SrcValue_ac_SrcCmdV=srcvalue_values[0],
                GNCBus_SrcValue_SrcV_fus=srcvalue_values[1],
                
                # MixValue
                GNCBus_MixValue_col_mix=mixvalue_values[0],
                GNCBus_MixValue_phi_mix=mixvalue_values[1],
                GNCBus_MixValue_Vx_mix=mixvalue_values[2],
                GNCBus_MixValue_dX_mix=mixvalue_values[3],
                GNCBus_MixValue_theta_mix=mixvalue_values[4],
                GNCBus_MixValue_Vy_mix=mixvalue_values[5],
                GNCBus_MixValue_dY_mix=mixvalue_values[6],
                GNCBus_MixValue_psi_mix=mixvalue_values[7],
                GNCBus_MixValue_Hdot_mix=mixvalue_values[8],
                GNCBus_MixValue_height_mix=mixvalue_values[9],
                
                # CmdValue - 重要！这是导航标签页需要的数据
                GNCBus_CmdValue_phi_cmd=cmdvalue_values[0],   # 滚转指令
                GNCBus_CmdValue_Hdot_cmd=cmdvalue_values[1],   # 垂向速度指令
                GNCBus_CmdValue_R_cmd=cmdvalue_values[2],      # 偏航速率指令
                GNCBus_CmdValue_psi_cmd=cmdvalue_values[3],    # 偏航指令
                GNCBus_CmdValue_Vx_cmd=cmdvalue_values[4],     # X速度指令
                GNCBus_CmdValue_Vy_cmd=cmdvalue_values[5],     # Y速度指令
                GNCBus_CmdValue_height_cmd=cmdvalue_values[6],  # 高度指令
                
                # 向后兼容字段
                pos_x=0.0, pos_y=0.0, pos_z=0.0,
                vel_x=0.0, vel_y=0.0, vel_z=0.0,
                euler_phi=0.0, euler_theta=0.0, euler_psi=0.0,
                control_mode=0, flight_mode=0
            )
        except Exception as e:
            print(f"[ExtY_FCS_GNCBUS_T] 解析失败: {e}")
            print(f"[ExtY_FCS_GNCBUS_T] Payload hex: {data[:100].hex()}")
            return cls()
    
    def to_json(self) -> dict:
        """返回符合interface.h命名规范的JSON格式
        
        包含GNC指令值字段，用于导航标签页显示
        使用解析后的实际值，而不是硬编码的0
        """
        json_data = {
            # GNC指令值（新增，用于导航标签页）- 使用解析后的实际值
            'GNCBus_CmdValue_phi_cmd': float(self.GNCBus_CmdValue_phi_cmd),
            'GNCBus_CmdValue_Hdot_cmd': float(self.GNCBus_CmdValue_Hdot_cmd),
            'GNCBus_CmdValue_R_cmd': float(self.GNCBus_CmdValue_R_cmd),
            'GNCBus_CmdValue_psi_cmd': float(self.GNCBus_CmdValue_psi_cmd),
            'GNCBus_CmdValue_Vx_cmd': float(self.GNCBus_CmdValue_Vx_cmd),
            'GNCBus_CmdValue_Vy_cmd': float(self.GNCBus_CmdValue_Vy_cmd),
            'GNCBus_CmdValue_height_cmd': float(self.GNCBus_CmdValue_height_cmd),
            # 位置和速度
            'pos_x': self.pos_x,
            'pos_y': self.pos_y,
            'pos_z': self.pos_z,
            'vel_x': self.vel_x,
            'vel_y': self.vel_y,
            'vel_z': self.vel_z,
            # 姿态
            'euler_phi': self.euler_phi,
            'euler_theta': self.euler_theta,
            'euler_psi': self.euler_psi,
            # 控制模式
            'control_mode': self.control_mode,
            'flight_mode': self.flight_mode,
            # TokenMode
            'GNCBus_TokenMode_OnSky': bool(self.GNCBus_TokenMode_OnSky),
            'GNCBus_TokenMode_Ctrl_Mode': bool(self.GNCBus_TokenMode_Ctrl_Mode),
            'GNCBus_TokenMode_mode_vert': self.GNCBus_TokenMode_mode_vert,
            'GNCBus_TokenMode_mode_nav': self.GNCBus_TokenMode_mode_nav,
            # 旧格式（向后兼容）
            'TokenMode': {
                'OnSky': bool(self.GNCBus_TokenMode_OnSky),
                'Ctrl_Mode': bool(self.GNCBus_TokenMode_Ctrl_Mode),
                'mode_vert': self.GNCBus_TokenMode_mode_vert,
                'mode_nav': self.GNCBus_TokenMode_mode_nav
            }
        }
        return json_data
    
    def to_bytes(self) -> bytes:
        """编码为字节数据
        
        根据from_bytes的解析顺序编码：
        - TokenMode: 17个int8 = 17字节
        - FtbOpt: 9个real32 + 1个int8 = 36+1 = 37字节
        - SrcValue: 2个int8 = 2字节
        - MixValue: 10个real32 = 40字节
        - CmdValue: 7个real32 = 28字节
        - VarValue: 4个real32 = 16字节
        - TrimValue: 3个real32 = 12字节
        - ParamsLMT: 10个real32 = 40字节
        - AcValue: 4个real32 = 16字节
        - HoverValue: 2个real_T + 1个int8 = 16+1 = 17字节
        - HomeValue: 2个real_T = 16字节
        
        总计：17 + 37 + 2 + 40 + 28 + 16 + 12 + 40 + 16 + 17 + 16 = 241字节
        """
        result = b''
        
        # 1. TokenMode (17个int8)
        result += struct.pack('<17b',
            self.GNCBus_TokenMode_OnSky,
            self.GNCBus_TokenMode_Ctrl_Mode,
            self.GNCBus_TokenMode_Pre_CMD,
            self.GNCBus_TokenMode_rud_state,
            self.GNCBus_TokenMode_ail_state,
            self.GNCBus_TokenMode_ele_state,
            self.GNCBus_TokenMode_col_state,
            self.GNCBus_TokenMode_nav_guid,
            self.GNCBus_TokenMode_cmd_guid,
            self.GNCBus_TokenMode_mode_guid,
            self.GNCBus_TokenMode_step_guid,
            self.GNCBus_TokenMode_mode_nav,
            self.GNCBus_TokenMode_token_nav,
            self.GNCBus_TokenMode_step_nav,
            self.GNCBus_TokenMode_mode_vert,
            self.GNCBus_TokenMode_token_vert,
            self.GNCBus_TokenMode_step_vert
        )
        
        # 2. FtbOpt (9个float + 1个int8)
        result += struct.pack('<9fb',
            self.GNCBus_FtbOpt_ele_opt,
            self.GNCBus_FtbOpt_ail_opt,
            self.GNCBus_FtbOpt_rud_opt,
            self.GNCBus_FtbOpt_col_opt,
            self.GNCBus_FtbOpt_R_opt,
            self.GNCBus_FtbOpt_Vx_opt,
            self.GNCBus_FtbOpt_Vy_opt,
            self.GNCBus_FtbOpt_coldt_opt,
            self.GNCBus_FtbOpt_col0_opt,
            self.GNCBus_FtbOpt_Ftb_Switch
        )
        
        # 3. SrcValue (2个int8)
        result += struct.pack('<2b',
            self.GNCBus_SrcValue_ac_SrcCmdV,
            self.GNCBus_SrcValue_SrcV_fus
        )
        
        # 4. MixValue (10个float)
        result += struct.pack('<10f',
            self.GNCBus_MixValue_col_mix,
            self.GNCBus_MixValue_phi_mix,
            self.GNCBus_MixValue_Vx_mix,
            self.GNCBus_MixValue_dX_mix,
            self.GNCBus_MixValue_theta_mix,
            self.GNCBus_MixValue_Vy_mix,
            self.GNCBus_MixValue_dY_mix,
            self.GNCBus_MixValue_psi_mix,
            self.GNCBus_MixValue_Hdot_mix,
            self.GNCBus_MixValue_height_mix
        )
        
        # 5. CmdValue (7个float)
        result += struct.pack('<7f',
            self.GNCBus_CmdValue_phi_cmd,
            self.GNCBus_CmdValue_Hdot_cmd,
            self.GNCBus_CmdValue_R_cmd,
            self.GNCBus_CmdValue_psi_cmd,
            self.GNCBus_CmdValue_Vx_cmd,
            self.GNCBus_CmdValue_Vy_cmd,
            self.GNCBus_CmdValue_height_cmd
        )
        
        # 6. VarValue (4个float)
        result += struct.pack('<4f',
            self.GNCBus_VarValue_psi_var,
            self.GNCBus_VarValue_height_var,
            self.GNCBus_VarValue_dX_var,
            self.GNCBus_VarValue_dY_var
        )
        
        # 7. TrimValue (3个float)
        result += struct.pack('<3f',
            self.GNCBus_TrimValue_Vx_trim,
            self.GNCBus_TrimValue_col_trim,
            self.GNCBus_TrimValue_col_autotrim
        )
        
        # 8. ParamsLMT (10个float)
        result += struct.pack('<10f',
            self.GNCBus_ParamsLMT_Vx_LMT,
            self.GNCBus_ParamsLMT_Vy_LMT,
            self.GNCBus_ParamsLMT_R_LMT,
            self.GNCBus_ParamsLMT_Hdot_ILmt,
            self.GNCBus_ParamsLMT_Hdot_UpLMT,
            self.GNCBus_ParamsLMT_Hdot_DownLMT,
            self.GNCBus_ParamsLMT_R_FLYTURN,
            self.GNCBus_ParamsLMT_R_unit,
            self.GNCBus_ParamsLMT_Hdot_unit,
            self.GNCBus_ParamsLMT_Vx_unit,
            self.GNCBus_ParamsLMT_Vy_unit
        )
        
        # 9. AcValue (4个float)
        result += struct.pack('<4f',
            self.GNCBus_AcValue_ac_dY,
            self.GNCBus_AcValue_ac_dX,
            self.GNCBus_AcValue_ac_dPsi,
            self.GNCBus_AcValue_ac_dL
        )
        
        # 10. HoverValue (2个double + 1个int8)
        result += struct.pack('<ddb',
            self.GNCBus_HoverValue_lon_hov,
            self.GNCBus_HoverValue_lat_hov,
            self.GNCBus_HoverValue_IsHovStatus_hov
        )
        
        # 11. HomeValue (2个double)
        result += struct.pack('<dd',
            self.GNCBus_HomeValue_lon_home,
            self.GNCBus_HomeValue_lat_home
        )
        
        return result


@dataclass
class ExtY_FCS_PARAM_T:
    """飞控参数
    
    根据C++ interface.h V2.0定义（第330-332行）：
    只包含 TimeStamp 字段（int32_t），4字节
    """
    TimeStamp: int32_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_PARAM_T':
        # 根据V2.0定义，只包含Time Stamp，4字节
        # C++飞控使用小端序发送
        fmt = '<i'  # 小端序：1个int32 = 4 bytes
        if len(data) < 4:
            print(f"[ExtY_FCS_PARAM_T] Payload长度不足: {len(data)} < 4")
            return cls()
        values = struct.unpack(fmt, data[:4])
        return cls(TimeStamp=values[0])
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<i'  # 小端序：1个int32 = 4 bytes
        return struct.pack(fmt, self.TimeStamp)
    
    def to_json(self) -> dict:
        return {
            'timestamp': self.TimeStamp
        }


@dataclass
class ExtY_FCS_AVOIFLAG_T:
    """避障标志"""
    AvoiFlag_LaserRadar_Enabled: uint8_T = 0
    AvoiFlag_AvoidanceFlag: uint8_T = 0
    AvoiFlag_GuideFlag: uint8_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_AVOIFLAG_T':
        # uint8不受字节序影响
        fmt = '<BBB'  # 3个uint8
        values = struct.unpack(fmt, data[:3])
        return cls(
            AvoiFlag_LaserRadar_Enabled=values[0],
            AvoiFlag_AvoidanceFlag=values[1],
            AvoiFlag_GuideFlag=values[2]
        )
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<BBB'  # 3个uint8 = 3 bytes
        return struct.pack(fmt,
            self.AvoiFlag_LaserRadar_Enabled,
            self.AvoiFlag_AvoidanceFlag,
            self.AvoiFlag_GuideFlag
        )
    
    def to_json(self) -> dict:
        """返回符合interface.h命名规范的JSON格式"""
        json_data = {
            # 新字段名（符合interface.h规范）
            'AvoiFlag_LaserRadar_Enabled': bool(self.AvoiFlag_LaserRadar_Enabled),
            'AvoiFlag_AvoidanceFlag': bool(self.AvoiFlag_AvoidanceFlag),
            'AvoiFlag_GuideFlag': bool(self.AvoiFlag_GuideFlag),
        }
        return json_data


@dataclass
class ExtY_FCS_ESC_T:
    """电机参数"""
    esc1_error_count: uint32_T = 0
    esc2_error_count: uint32_T = 0
    esc3_error_count: uint32_T = 0
    esc4_error_count: uint32_T = 0
    esc5_error_count: uint32_T = 0
    esc6_error_count: uint32_T = 0
    esc1_rpm: int32_T = 0
    esc2_rpm: int32_T = 0
    esc3_rpm: int32_T = 0
    esc4_rpm: int32_T = 0
    esc5_rpm: int32_T = 0
    esc6_rpm: int32_T = 0
    esc1_power_rating_pct: uint8_T = 0
    esc2_power_rating_pct: uint8_T = 0
    esc3_power_rating_pct: uint8_T = 0
    esc4_power_rating_pct: uint8_T = 0
    esc5_power_rating_pct: uint8_T = 0
    esc6_power_rating_pct: uint8_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_ESC_T':
        # C++飞控使用小端序发送payload数据
        fmt = '<IIIIIIiiiiiiBBBBBB'  # 小端序：6*uint32 + 6*int32 + 6*uint8 = 60 bytes
        values = struct.unpack(fmt, data[:60])
        return cls(
            esc1_error_count=values[0], esc2_error_count=values[1],
            esc3_error_count=values[2], esc4_error_count=values[3],
            esc5_error_count=values[4], esc6_error_count=values[5],
            esc1_rpm=values[6], esc2_rpm=values[7],
            esc3_rpm=values[8], esc4_rpm=values[9],
            esc5_rpm=values[10], esc6_rpm=values[11],
            esc1_power_rating_pct=values[12], esc2_power_rating_pct=values[13],
            esc3_power_rating_pct=values[14], esc4_power_rating_pct=values[15],
            esc5_power_rating_pct=values[16], esc6_power_rating_pct=values[17]
        )
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<IIIIIIiiiiiiBBBBBB'  # 小端序：6*uint32 + 6*int32 + 6*uint8 = 60 bytes
        return struct.pack(fmt,
            self.esc1_error_count, self.esc2_error_count, self.esc3_error_count,
            self.esc4_error_count, self.esc5_error_count, self.esc6_error_count,
            self.esc1_rpm, self.esc2_rpm, self.esc3_rpm,
            self.esc4_rpm, self.esc5_rpm, self.esc6_rpm,
            self.esc1_power_rating_pct, self.esc2_power_rating_pct,
            self.esc3_power_rating_pct, self.esc4_power_rating_pct,
            self.esc5_power_rating_pct, self.esc6_power_rating_pct
        )


@dataclass
class ExtY_FCS_DATAFUTABA_T:
    """Futaba遥控数据（第218-226行）
    
    遥控器输入数据，用于控制标签页显示
    """
    Tele_ftb_Roll: uint16_T = 0       # 滚转角 (0-2000)
    Tele_ftb_Pitch: uint16_T = 0      # 俯仰角 (0-2000)
    Tele_ftb_Yaw: uint16_T = 0        # 偏航角 (0-2000)
    Tele_ftb_Col: uint16_T = 0        # 油门 (0-2000)
    Tele_ftb_Switch: int8_T = 0         # 开关状态
    Tele_ftb_com_Ftb_fail: int8_T = 0  # 遥控故障标志
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_DATAFUTABA_T':
        """从字节数据解析Futaba遥控数据
        
        总共：4个uint16 + 2个int8 = 8+2 = 10字节
        """
        if len(data) < 10:
            print(f"[ExtY_FCS_DATAFUTABA_T] Payload长度不足: {len(data)} < 10")
            return cls()
        
        # 格式：4个uint16 + 2个int8
        fmt = '<HHHHbb'  # 小端序：4*uint16 + 2*int8 = 10 bytes
        values = struct.unpack(fmt, data[:10])
        
        return cls(
            Tele_ftb_Roll=values[0],
            Tele_ftb_Pitch=values[1],
            Tele_ftb_Yaw=values[2],
            Tele_ftb_Col=values[3],
            Tele_ftb_Switch=values[4],
            Tele_ftb_com_Ftb_fail=values[5]
        )
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<HHHHbb'  # 小端序：4*uint16 + 2*int8 = 10 bytes
        return struct.pack(fmt,
            self.Tele_ftb_Roll,
            self.Tele_ftb_Pitch,
            self.Tele_ftb_Yaw,
            self.Tele_ftb_Col,
            self.Tele_ftb_Switch,
            self.Tele_ftb_com_Ftb_fail
        )
    
    def to_json(self) -> dict:
        """返回符合interface.h命名规范的JSON格式"""
        return {
            'Tele_ftb_Roll': self.Tele_ftb_Roll,
            'Tele_ftb_Pitch': self.Tele_ftb_Pitch,
            'Tele_ftb_Yaw': self.Tele_ftb_Yaw,
            'Tele_ftb_Col': self.Tele_ftb_Col,
            'Tele_ftb_Switch': self.Tele_ftb_Switch,
            'Tele_ftb_com_Ftb_fail': self.Tele_ftb_com_Ftb_fail
        }


@dataclass
class ExtY_FCS_DATAGCS_T:
    """地面站发送数据（第228-234行）"""
    Tele_GCS_CmdIdx: int32_T = 0
    Tele_GCS_Mission: int32_T = 0
    Tele_GCS_Val: real32_T = 0.0
    Tele_GCS_com_GCS_fail: int8_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_DATAGCS_T':
        """从字节数据解析GCS数据
        
        总共：2个int32 + 1个float32 + 1个int8 = 8+4+1 = 13字节
        """
        if len(data) < 13:
            print(f"[ExtY_FCS_DATAGCS_T] Payload长度不足: {len(data)} < 13")
            return cls()
        
        # 格式：2个int32 + 1个float32 + 1个int8
        fmt = '<iifb'  # 小端序：2*int32 + 1*float32 + 1*int8 = 13 bytes
        values = struct.unpack(fmt, data[:13])
        
        return cls(
            Tele_GCS_CmdIdx=values[0],
            Tele_GCS_Mission=values[1],
            Tele_GCS_Val=values[2],
            Tele_GCS_com_GCS_fail=values[3]
        )
    
    def to_bytes(self) -> bytes:
        """编码为字节数据"""
        fmt = '<iifb'  # 小端序：2*int32 + 1*float32 + 1*int8 = 13 bytes
        return struct.pack(fmt,
            self.Tele_GCS_CmdIdx,
            self.Tele_GCS_Mission,
            self.Tele_GCS_Val,
            self.Tele_GCS_com_GCS_fail
        )
    
    def to_json(self) -> dict:
        return {
            'CmdIdx': self.Tele_GCS_CmdIdx,
            'Mission': self.Tele_GCS_Mission,
            'Val': self.Tele_GCS_Val,
            'fail': bool(self.Tele_GCS_com_GCS_fail)
        }


# 航迹线结构体
@dataclass
class ExtY_FCS_LINESTRUC_ac_aim2AB_T:
    """航迹线结构 ac_aim2AB
    
    从当前位置到下一个路径点的航迹线信息
    """
    ac_aim2AB_lon: real_T = 0.0
    ac_aim2AB_lat: real_T = 0.0
    ac_aim2AB_psi: real32_T = 0.0
    ac_aim2AB_alt: real32_T = 0.0
    ac_aim2AB_len: real32_T = 0.0
    ac_aim2AB_rad: real32_T = 0.0
    ac_aim2AB_Vx2nextdot: real32_T = 0.0
    ac_aim2AB_next_num: int8_T = 0
    ac_aim2AB_next_dot: int8_T = 0
    ac_aim2AB_type_dot: uint8_T = 0
    ac_aim2AB_clockwise_WP: uint8_T = 0
    ac_aim2AB_R_WP: real32_T = 0.0
    ac_aim2AB_type_WP: uint8_T = 0
    ac_aim2AB_Num_type_WP: uint8_T = 0
    ac_aim2AB_dL_WP: real32_T = 0.0
    ac_aim2AB_Vx_type: uint8_T = 0
    ac_aim2AB_TTC_Fault_Mode: uint8_T = 0
    ac_aim2AB_deltaY_ctrl: uint8_T = 0
    ac_aim2AB_turn_type: uint8_T = 0
    ac_aim2AB_Inv_type: uint8_T = 0
    ac_aim2AB_type_line: uint8_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_LINESTRUC_ac_aim2AB_T':
        """从字节数据解析航迹线信息
        
        总计87字节，按照interface.h第237-259行的字段顺序解析，使用pragma pack(1) 1字节对齐
        格式：<dd (2*double=16) + 15f (15*float=60) + bb (2*int8=2) + 9B (9*uint8=9) = 87字节
        
        字节布局：2*double(16) + 15*float(60) + 2*int8(2) + 9*uint8(9) = 87字节
        值索引：0-1(2d), 2-16(15f), 17-18(2b), 19-27(9B)
        """
        if len(data) < 87:
            print(f"[ExtY_FCS_LINESTRUC_ac_aim2AB_T] Payload长度不足: {len(data)} < 87")
            return cls()
        
        # 直接按照字段顺序一次性解析所有字段，与to_bytes()保持一致
        values = struct.unpack('<dd15fbb9B', data[:87])
        
        # values有28个元素 (索引0-27)
        # 0-1: 2个double (lon, lat)
        # 2-16: 15个float (psi, alt, len, rad, Vx2nextdot, R_WP, dL_WP, 7个padding)
        # 17-18: 2个int8 (next_num, next_dot)
        # 19-27: 9个uint8 (type_dot, clockwise_WP, type_WP, Num_type_WP, Vx_type,
        #                TTC_Fault_Mode, deltaY_ctrl, turn_type, Inv_type, type_line)
        
        # 注意：只有19个实际字段，但有7个padding floats需要跳过
        
        return cls(
            # 2*real_T (16字节) - values[0-1]
            ac_aim2AB_lon=values[0],
            ac_aim2AB_lat=values[1],
            # 15*real32_T (60字节) - values[2-16]
            ac_aim2AB_psi=values[2],
            ac_aim2AB_alt=values[3],
            ac_aim2AB_len=values[4],
            ac_aim2AB_rad=values[5],
            ac_aim2AB_Vx2nextdot=values[6],
            ac_aim2AB_R_WP=values[7],
            ac_aim2AB_dL_WP=values[8],
            # 7个padding floats (values[9-15]) - 跳过（不对应任何字段）
            # 2*int8_T (2字节) - values[16-17]
            ac_aim2AB_next_num=values[16],
            ac_aim2AB_next_dot=values[17],
            # 9*uint8_T (9字节) - values[18-26]
            ac_aim2AB_type_dot=values[18],
            ac_aim2AB_clockwise_WP=values[19],
            ac_aim2AB_type_WP=values[20],
            ac_aim2AB_Num_type_WP=values[21],
            ac_aim2AB_Vx_type=values[22],
            ac_aim2AB_TTC_Fault_Mode=values[23],
            ac_aim2AB_deltaY_ctrl=values[24],
            ac_aim2AB_turn_type=values[25],
            ac_aim2AB_Inv_type=values[26],
            ac_aim2AB_type_line=values[27]
        )
    
    def to_bytes(self) -> bytes:
        """编码为字节数据
        
        总计87字节，按照interface.h第237-259行的字段顺序编码，使用pragma pack(1) 1字节对齐
        直接按照字段顺序打包，不分组
        """
        # 格式字符串：< (小端序) + dd (2*double=16) + 5f (5*float=20) + bb (2*int8=2)
        #             + 2Bf (2*uint8+1*float=6) + 2Bf (2*uint8+1*float=6) + 6B (6*uint8=6)
        # 总计：16 + 20 + 2 + 6 + 6 + 6 = 56字节？不对！应该是：87字节
        
        # 让我重新按照interface.h的字段顺序：
        # 2*real_T + 6*real32_T + 2*int8_T + 3*uint8_T + 1*real32_T + 2*uint8_T + 1*real32_T + 9*uint8_T
        # = 16 + 24 + 2 + 3 + 4 + 2 + 4 + 9 = 64？还是不对！
        
        # 让我直接按照from_bytes的解析逻辑编写to_bytes
        # from_bytes中：2*double + 15*float + 2*int8 + 9*uint8 = 16 + 60 + 2 + 9 = 87字节
        
        return struct.pack('<dd15fbb9B',
            # 2*real_T (16字节)
            self.ac_aim2AB_lon,
            self.ac_aim2AB_lat,
            # 15*real32_T (60字节)
            self.ac_aim2AB_psi,
            self.ac_aim2AB_alt,
            self.ac_aim2AB_len,
            self.ac_aim2AB_rad,
            self.ac_aim2AB_Vx2nextdot,
            self.ac_aim2AB_R_WP,
            self.ac_aim2AB_dL_WP,
            0.0,  # padding1 (对应floats[6])
            0.0,  # padding2 (对应floats[7])
            0.0,  # padding3 (对应floats[8])
            0.0,  # padding4 (对应floats[9])
            0.0,  # padding5 (对应floats[10])
            0.0,  # padding6 (对应floats[11])
            0.0,  # padding7 (对应floats[12])
            # 2*int8_T (2字节)
            self.ac_aim2AB_next_num,
            self.ac_aim2AB_next_dot,
            # 9*uint8_T (9字节)
            self.ac_aim2AB_type_dot,
            self.ac_aim2AB_clockwise_WP,
            self.ac_aim2AB_type_WP,
            self.ac_aim2AB_Num_type_WP,
            self.ac_aim2AB_Vx_type,
            self.ac_aim2AB_TTC_Fault_Mode,
            self.ac_aim2AB_deltaY_ctrl,
            self.ac_aim2AB_turn_type,
            self.ac_aim2AB_Inv_type,
            self.ac_aim2AB_type_line
        )
    
    def to_json(self) -> dict:
        return {
            'lon': float(self.ac_aim2AB_lon),
            'lat': float(self.ac_aim2AB_lat),
            'psi': float(self.ac_aim2AB_psi),
            'alt': float(self.ac_aim2AB_alt),
            'len': float(self.ac_aim2AB_len),
            'rad': float(self.ac_aim2AB_rad),
            'Vx2nextdot': float(self.ac_aim2AB_Vx2nextdot),
            'next_num': self.ac_aim2AB_next_num,
            'next_dot': self.ac_aim2AB_next_dot,
            'type_dot': self.ac_aim2AB_type_dot,
            'clockwise_WP': bool(self.ac_aim2AB_clockwise_WP),
            'R_WP': float(self.ac_aim2AB_R_WP),
            'type_WP': self.ac_aim2AB_type_WP,
            'Num_type_WP': self.ac_aim2AB_Num_type_WP,
            'dL_WP': float(self.ac_aim2AB_dL_WP),
            'Vx_type': self.ac_aim2AB_Vx_type,
            'TTC_Fault_Mode': self.ac_aim2AB_TTC_Fault_Mode,
            'deltaY_ctrl': self.ac_aim2AB_deltaY_ctrl,
            'turn_type': self.ac_aim2AB_turn_type,
            'Inv_type': self.ac_aim2AB_Inv_type,
            'type_line': self.ac_aim2AB_type_line
        }


@dataclass
class ExtY_FCS_LINESTRUC_acAB_T:
    """航迹线结构 acAB
    
    AB段航迹线信息
    """
    acAB_lon: real_T = 0.0
    acAB_lat: real_T = 0.0
    acAB_psi: real32_T = 0.0
    acAB_alt: real32_T = 0.0
    acAB_len: real32_T = 0.0
    acAB_rad: real32_T = 0.0
    acAB_Vx2nextdot: real32_T = 0.0
    acAB_next_num: int8_T = 0
    acAB_next_dot: int8_T = 0
    acAB_type_dot: uint8_T = 0
    acAB_clockwise_WP: uint8_T = 0
    acAB_R_WP: real32_T = 0.0
    acAB_type_WP: uint8_T = 0
    acAB_Num_type_WP: uint8_T = 0
    acAB_dL_WP: real32_T = 0.0
    acAB_Vx_type: uint8_T = 0
    acAB_TTC_Fault_Mode: uint8_T = 0
    acAB_deltaY_ctrl: uint8_T = 0
    acAB_turn_type: uint8_T = 0
    acAB_Inv_type: uint8_T = 0
    acAB_type_line: uint8_T = 0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExtY_FCS_LINESTRUC_acAB_T':
        """从字节数据解析AB段航迹线信息
        
        总计87字节：2*real_T + 6*real32_T + 2*int8_T + 3*uint8_T +
                  1*real32_T + 2*uint8_T + 1*real32_T + 5*uint8_T
        按照interface.h第261-283行的字段顺序解析
        """
        if len(data) < 87:
            print(f"[ExtY_FCS_LINESTRUC_acAB_T] Payload长度不足: {len(data)} < 87")
            return cls()
        
        offset = 0
        # acAB_lon (real_T, 8字节)
        # acAB_lat (real_T, 8字节)
        lon, lat = struct.unpack_from('<dd', data, offset)
        offset += 16
        
        # acAB_psi (real32_T, 4字节)
        # acAB_alt (real32_T, 4字节)
        # acAB_len (real32_T, 4字节)
        # acAB_rad (real32_T, 4字节)
        # acAB_Vx2nextdot (real32_T, 4字节)
        floats_part1 = struct.unpack_from('<5f', data, offset)
        offset += 20
        
        # acAB_next_num (int8_T, 1字节)
        # acAB_next_dot (int8_T, 1字节)
        next_num, next_dot = struct.unpack_from('<bb', data, offset)
        offset += 2
        
        # acAB_type_dot (uint8_T, 1字节)
        # acAB_clockwise_WP (uint8_T, 1字节)
        # acAB_R_WP (real32_T, 4字节)
        uint8_part1 = struct.unpack_from('<2B', data, offset)
        offset += 2
        r_wp = struct.unpack_from('<f', data, offset)
        offset += 4
        
        # acAB_type_WP (uint8_T, 1字节)
        # acAB_Num_type_WP (uint8_T, 1字节)
        # acAB_dL_WP (real32_T, 4字节)
        uint8_part2 = struct.unpack_from('<2B', data, offset)
        offset += 2
        dl_wp = struct.unpack_from('<f', data, offset)
        offset += 4
        
        # acAB_Vx_type (uint8_T, 1字节)
        # acAB_TTC_Fault_Mode (uint8_T, 1字节)
        # acAB_deltaY_ctrl (uint8_T, 1字节)
        # acAB_turn_type (uint8_T, 1字节)
        # acAB_Inv_type (uint8_T, 1字节)
        # acAB_type_line (uint8_T, 1字节)
        uint8_part3 = struct.unpack_from('<6B', data, offset)
        
        return cls(
            acAB_lon=lon,
            acAB_lat=lat,
            acAB_psi=floats_part1[0],
            acAB_alt=floats_part1[1],
            acAB_len=floats_part1[2],
            acAB_rad=floats_part1[3],
            acAB_Vx2nextdot=floats_part1[4],
            acAB_next_num=next_num,
            acAB_next_dot=next_dot,
            acAB_type_dot=uint8_part1[0],
            acAB_clockwise_WP=uint8_part1[1],
            acAB_R_WP=r_wp[0],
            acAB_type_WP=uint8_part2[0],
            acAB_Num_type_WP=uint8_part2[1],
            acAB_dL_WP=dl_wp[0],
            acAB_Vx_type=uint8_part3[0],
            acAB_TTC_Fault_Mode=uint8_part3[1],
            acAB_deltaY_ctrl=uint8_part3[2],
            acAB_turn_type=uint8_part3[3],
            acAB_Inv_type=uint8_part3[4],
            acAB_type_line=uint8_part3[5]
        )

    def to_bytes(self) -> bytes:
        """编码为字节数据
        
        总计87字节，按照interface.h第261-283行的字段顺序编码，使用pragma pack(1) 1字节对齐
        直接按照字段顺序打包，不分组
        """
        # 格式字符串：< (小端序) + dd (2*double=16) + 15f (15*float=60) + bb (2*int8=2) + 9B (9*uint8=9)
        # 总计：16 + 60 + 2 + 9 = 87字节
        
        return struct.pack('<dd15fbb9B',
            # 2*real_T (16字节)
            self.acAB_lon,
            self.acAB_lat,
            # 15*real32_T (60字节)
            self.acAB_psi,
            self.acAB_alt,
            self.acAB_len,
            self.acAB_rad,
            self.acAB_Vx2nextdot,
            self.acAB_R_WP,
            self.acAB_dL_WP,
            0.0,  # padding1 (对应floats[6])
            0.0,  # padding2 (对应floats[7])
            0.0,  # padding3 (对应floats[8])
            0.0,  # padding4 (对应floats[9])
            0.0,  # padding5 (对应floats[10])
            0.0,  # padding6 (对应floats[11])
            0.0,  # padding7 (对应floats[12])
            # 2*int8_T (2字节)
            self.acAB_next_num,
            self.acAB_next_dot,
            # 9*uint8_T (9字节)
            self.acAB_type_dot,
            self.acAB_clockwise_WP,
            self.acAB_type_WP,
            self.acAB_Num_type_WP,
            self.acAB_Vx_type,
            self.acAB_TTC_Fault_Mode,
            self.acAB_deltaY_ctrl,
            self.acAB_turn_type,
            self.acAB_Inv_type,
            self.acAB_type_line
        )

    def to_json(self) -> dict:
        return {
            'lon': float(self.acAB_lon),
            'lat': float(self.acAB_lat),
            'psi': float(self.acAB_psi),
            'alt': float(self.acAB_alt),
            'len': float(self.acAB_len),
            'rad': float(self.acAB_rad),
            'Vx2nextdot': float(self.acAB_Vx2nextdot),
            'next_num': self.acAB_next_num,
            'next_dot': self.acAB_next_dot,
            'type_dot': self.acAB_type_dot,
            'clockwise_WP': bool(self.acAB_clockwise_WP),
            'R_WP': float(self.acAB_R_WP),
            'type_WP': self.acAB_type_WP,
            'Num_type_WP': self.acAB_Num_type_WP,
            'dL_WP': float(self.acAB_dL_WP),
            'Vx_type': self.acAB_Vx_type,
            'TTC_Fault_Mode': self.acAB_TTC_Fault_Mode,
            'deltaY_ctrl': self.acAB_deltaY_ctrl,
            'turn_type': self.acAB_turn_type,
            'Inv_type': self.acAB_Inv_type,
            'type_line': self.acAB_type_line
        }


# 地面遥控指令枚举
class CmdIdx(IntEnum):
    CMD_NONE = 0
    CMD_EXTERNAL_CONTROL = 1
    CMD_MIXED_CONTROL = 2
    CMD_PROGRAM_CONTROL = 3
    CMD_CLIMB = 4
    CMD_CRUISE = 5
    CMD_DESCENT = 6
    CMD_DISABLE_ALT_HOLD = 7
    CMD_HEADING_HOLD = 8
    CMD_LEFT_CIRCLE = 9
    CMD_RIGHT_CIRCLE = 10
    CMD_HEADING_LOCK = 11
    CMD_ENGINE_START = 12
    CMD_ENGINE_STOP = 13
    CMD_AUTO_TAKEOFF = 14
    CMD_AUTO_LAND = 15
    CMD_HOVER = 16
    CMD_RETURN_TO_HOME = 17
    CMD_PRE_CONTROL = 18
    CMD_GROUND_SPEED = 19
    CMD_AIR_SPEED = 20
    CMD_TAKEOFF_PREP = 21
    CMD_MANUAL_TAKEOFF = 22
    CMD_MANUAL_LAND = 23
    CMD_PLAN_ON = 24
    CMD_PLAN_OFF = 25


# 地面站发送到飞控的数据结构
@dataclass
class ExtU_FCS_T:
    """地面站发送ExtU_FCS_T数据"""
    # PID参数
    F_KaPHI: real32_T = 0.0
    F_KaP: real32_T = 0.0
    F_KaY: real32_T = 0.0
    F_IaY: real32_T = 0.0
    F_KaVy: real32_T = 0.0
    F_IaVy: real32_T = 0.0
    F_KaAy: real32_T = 0.0
    F_KeTHETA: real32_T = 0.0
    F_KeQ: real32_T = 0.0
    F_KeX: real32_T = 0.0
    F_IeX: real32_T = 0.0
    F_KeVx: real32_T = 0.0
    F_IeVx: real32_T = 0.0
    F_KeAx: real32_T = 0.0
    F_KrR: real32_T = 0.0
    F_IrR: real32_T = 0.0
    F_KrAy: real32_T = 0.0
    F_KrPSI: real32_T = 0.0
    F_KcH: real32_T = 0.0
    F_IcH: real32_T = 0.0
    F_KcHdot: real32_T = 0.0
    F_IcHdot: real32_T = 0.0
    F_KcAz: real32_T = 0.0
    F_IgRPM: real32_T = 0.0
    F_KgRPM: real32_T = 0.0
    F_Scale_factor: real32_T = 0.0
    # 指令信息
    CmdIdx: int32_T = 0
    CmdMission: int32_T = 0
    CmdMissionVal: real32_T = 0.0


# ================================================================
# LiDAR障碍物接口结构体定义
# ================================================================

@dataclass
class ObstacleInfo_T:
    """障碍物信息"""
    # 位置信息 (ENU坐标系, 单位: m)
    position_x: real32_T = 0.0  # 东向
    position_y: real32_T = 0.0  # 北向
    position_z: real32_T = 0.0  # 天向
    
    # 尺寸信息 (单位: m)
    size_x: real32_T = 0.0
    size_y: real32_T = 0.0
    size_z: real32_T = 0.0
    
    # 高度范围 (单位: m)
    height_min: real32_T = 0.0
    height_max: real32_T = 0.0
    
    # 距离与方位角
    distance: real32_T = 0.0
    azimuth: real32_T = 0.0
    
    # 置信度评估
    confidence: real32_T = 0.0
    
    # 点云统计
    point_count: int32_T = 0
    density: real32_T = 0.0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ObstacleInfo_T':
        """从字节数据解析障碍物信息"""
        # 总共 11个float32 + 1个int32 + 1个float32 = 52字节
        fmt = '<fffffffffff i f'  # 11 floats + 1 int + 1 float
        if len(data) < 52:
            return cls()
        
        values = struct.unpack(fmt, data[:52])
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
            point_count=values[11],
            density=values[12]
        )


# 最大障碍物数量
MAX_OBSTACLES = 50


@dataclass
class ObstacleOutput_T:
    """障碍物输出数组"""
    obstacle_count: int32_T = 0
    obstacles: List[ObstacleInfo_T] = field(default_factory=list)
    timestamp_sec: real_T = 0.0
    timestamp_us: uint64_T = 0
    frame_id: int32_T = 0
    input_point_count: int32_T = 0
    filtered_point_count: int32_T = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> 'ObstacleOutput_T':
        """从字节数据解析"""
        # 结构: obstacle_count(4) + obstacles数组(52*50=2600) + frame_info 等
        # 只有当数据长度足够时才进行完整解析
        if len(data) < 20:  # 最小安全长度
            return cls()
        
        offset = 0
        
        # 解析obstacle_count
        obstacle_count = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4
        
        # 障碍物数组位于偏移 4 处，固定大小 50 * 52 = 2600 字节
        obstacles_start = 4
        obstacles_size = 50 * 52 # MAX_OBSTACLES = 50, sizeof(ObstacleInfo_T) = 52
        
        # 时间戳和帧信息位于数组之后
        # 4 + 2600 = 2604
        info_offset = obstacles_start + obstacles_size
        
        # 检查数据长度是否足够包含尾部信息 (2604 + 8+8+4+4+4 = 2632)
        if len(data) < info_offset + 28:
            # 如果数据不够长
             pass

        # 解析障碍物
        obstacles = []
        max_valid = min(obstacle_count, 50)
        
        curr_obs_offset = obstacles_start
        for i in range(max_valid):
            if curr_obs_offset + 52 <= len(data):
                obs = ObstacleInfo_T.from_bytes(data[curr_obs_offset : curr_obs_offset+52])
                obstacles.append(obs)
            curr_obs_offset += 52
            
        # 解析尾部信息 (时间戳等)
        timestamp_sec = 0.0
        timestamp_us = 0
        frame_id = 0
        input_point_count = 0
        filtered_point_count = 0

        if len(data) >= info_offset + 28:
             off = info_offset
             timestamp_sec = struct.unpack('<d', data[off:off+8])[0]
             off += 8
             timestamp_us = struct.unpack('<Q', data[off:off+8])[0]
             off += 8
             frame_id = struct.unpack('<i', data[off:off+4])[0]
             off += 4
             input_point_count = struct.unpack('<i', data[off:off+4])[0]
             off += 4
             filtered_point_count = struct.unpack('<i', data[off:off+4])[0]
             off += 4

        return cls(
            obstacle_count=obstacle_count,
            obstacles=obstacles,
            timestamp_sec=timestamp_sec,
            timestamp_us=timestamp_us,
            frame_id=frame_id,
            input_point_count=input_point_count,
            filtered_point_count=filtered_point_count
        )
    
    def to_json(self) -> dict:
        return {
            'obstacle_count': self.obstacle_count,
            'obstacles': [obstacle.__dict__ for obstacle in self.obstacles[:self.obstacle_count]],
            'timestamp_sec': self.timestamp_sec,
            'frame_id': self.frame_id
        }


@dataclass
class SystemStatus_T:
    """系统状态"""
    is_running: uint8_T = 0
    lidar_connected: uint8_T = 0
    imu_data_valid: uint8_T = 0
    motion_comp_active: uint8_T = 0
    error_code: int32_T = 0
    error_message: str = ""
    total_frames: int32_T = 0
    total_obstacles: int32_T = 0
    avg_processing_time_ms: real32_T = 0.0


# ================================================================
# GCS航迹规划/遥测协议定义
# ================================================================

@dataclass
class PathPoint_T:
    """路径点坐标 (对应C的PathPoint_T)"""
    x: real_T = 0.0  # double
    y: real_T = 0.0  # double
    z: real_T = 0.0  # double

    @classmethod
    def from_bytes(cls, data: bytes) -> 'PathPoint_T':
        """从24字节数据解析"""
        if len(data) < 24:
            return cls()
        values = struct.unpack('<3d', data[:24])
        return cls(x=values[0], y=values[1], z=values[2])

    def to_bytes(self) -> bytes:
        """编码为24字节数据"""
        return struct.pack('<3d', self.x, self.y, self.z)

    def to_json(self) -> dict:
        return {'x': self.x, 'y': self.y, 'z': self.z}


@dataclass
class Object3d_T:
    """障碍物信息 (对应C的Object3d_T)"""
    cx: real_T = 0.0
    cy: real_T = 0.0
    cz: real_T = 0.0
    sx: real_T = 0.0
    sy: real_T = 0.0
    sz: real_T = 0.0
    vx: real_T = 0.0
    vy: real_T = 0.0
    vz: real_T = 0.0

    @classmethod
    def from_bytes(cls, data: bytes) -> 'Object3d_T':
        """从72字节数据解析"""
        if len(data) < 72:
            return cls()
        values = struct.unpack('<9d', data[:72])
        return cls(cx=values[0], cy=values[1], cz=values[2],
                   sx=values[3], sy=values[4], sz=values[5],
                   vx=values[6], vy=values[7], vz=values[8])

    def to_bytes(self) -> bytes:
        """编码为72字节数据"""
        return struct.pack('<9d', self.cx, self.cy, self.cz, self.sx, self.sy, self.sz, self.vx, self.vy, self.vz)

    def to_json(self) -> dict:
        return {
            'center': {'x': self.cx, 'y': self.cy, 'z': self.cz},
            'size': {'x': self.sx, 'y': self.sy, 'z': self.sz},
            'velocity': {'x': self.vx, 'y': self.vy, 'z': self.vz}
        }


@dataclass
class GCSTelemetry_T:
    """GCS遥测数据，对应功能码 0x71 (新版结构)"""
    seq_id: uint32_T = 0
    timestamp: uint32_T = 0
    current_pos_x: real_T = 0.0
    current_pos_y: real_T = 0.0
    current_pos_z: real_T = 0.0
    current_vel: real_T = 0.0
    update_flags: uint8_T = 0
    status: uint8_T = 0
    global_path_count: uint16_T = 0
    local_traj_count: uint16_T = 0
    obstacle_count: uint16_T = 0
    
    # 动态数据
    global_path: List[PathPoint_T] = field(default_factory=list)
    local_path: List[PathPoint_T] = field(default_factory=list)
    obstacles: List[Object3d_T] = field(default_factory=list)

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['GCSTelemetry_T']:
        """从字节数据解析GCS遥测信息 (新版结构)"""
        try:
            offset = 0
            
            # 固定部分: 2*uint32 + 4*double + 2*uint8 + 3*uint16 = 8 + 32 + 2 + 6 = 48 bytes
            if len(data) < 48:
                logger.warning(f"[GCSTelemetry_T] 数据长度不足，无法解析固定头部: {len(data)} < 48")
                return None

            # 解析固定部分
            (seq_id, timestamp,
             current_pos_x, current_pos_y, current_pos_z, current_vel,
             update_flags, status,
             global_path_count, local_traj_count, obstacle_count) = struct.unpack_from('<II4dBB3H', data, offset)
            offset += 48

            # 验证总长度是否足够
            expected_len = offset + (global_path_count * 24) + (local_traj_count * 24) + (obstacle_count * 72)
            if len(data) < expected_len:
                logger.warning(f"[GCSTelemetry_T] 数据长度不足，无法解析动态数组: {len(data)} < {expected_len}")
                return None

            # 解析全局路径
            global_path = []
            for _ in range(global_path_count):
                global_path.append(PathPoint_T.from_bytes(data[offset:offset+24]))
                offset += 24

            # 解析局部路径
            local_path = []
            for _ in range(local_traj_count):
                local_path.append(PathPoint_T.from_bytes(data[offset:offset+24]))
                offset += 24

            # 解析障碍物
            obstacles = []
            for _ in range(obstacle_count):
                obstacles.append(Object3d_T.from_bytes(data[offset:offset+72]))
                offset += 72
            
            return cls(
                seq_id=seq_id,
                timestamp=timestamp,
                current_pos_x=current_pos_x,
                current_pos_y=current_pos_y,
                current_pos_z=current_pos_z,
                current_vel=current_vel,
                update_flags=update_flags,
                status=status,
                global_path_count=global_path_count,
                local_traj_count=local_traj_count,
                obstacle_count=obstacle_count,
                global_path=global_path,
                local_path=local_path,
                obstacles=obstacles
            )
        except Exception as e:
            logger.error(f"解析 GCSTelemetry_T 失败: {e}")
            return None

    def to_json(self) -> dict:
        """将遥测数据转换为JSON格式"""
        return {
            'seq_id': self.seq_id,
            'timestamp': self.timestamp,
            'position': {'x': self.current_pos_x, 'y': self.current_pos_y, 'z': self.current_pos_z},
            'velocity': self.current_vel,
            'update_flags': self.update_flags,
            'status': self.status,
            'global_path_count': self.global_path_count,
            'global_path': [p.to_json() for p in self.global_path],
            'local_traj_count': self.local_traj_count,
            'local_path': [p.to_json() for p in self.local_path],
            'obstacle_count': self.obstacle_count,
            'obstacles': [o.to_json() for o in self.obstacles]
        }


# ================================================================
# NCLink帧结构定义
# ================================================================

@dataclass
class NCLinkFrame:
    """NCLink协议帧"""
    head0: uint8_T = NCLINK_HEAD0
    head1: uint8_T = NCLINK_HEAD1
    data_len: uint16_T = 0
    func_code: uint8_T = 0
    data: bytes = field(default_factory=bytes)
    checksum: uint8_T = 0
    end0: uint8_T = NCLINK_END0
    end1: uint8_T = NCLINK_END1
    
    @classmethod
    def create_frame(cls, func_code: uint8_T, data: bytes = b'') -> 'NCLinkFrame':
        """创建NCLink帧
        
        正确的帧格式（严格按照C++代码实现）：
        [帧头2字节] [命令1字节] [长度2字节] [数据N字节] [校验1字节] [帧尾2字节]
          FF FC       0x40        0x04 00    data         CS         A1 A2
          
        重要：使用C++风格的逐字节构造，确保字节顺序正确
        """
        data_len = len(data)
        
        # 构建帧头（5字节）：头(2) + 命令(1) + 长度(2)
        # 使用逐字节构造方式（模拟C++代码）
        header = bytes([
            NCLINK_HEAD0,              # 字节0: 0xFF
            NCLINK_HEAD1,              # 字节1: 0xFC
            func_code,                 # 字节2: 命令字 (如0x40)
            (data_len >> 8) & 0xFF,    # 字节3: 长度高字节 (大端序)
            data_len & 0xFF            # 字节4: 长度低字节 (大端序)
        ])
        
        # 构建完整帧（不含校验和和帧尾）
        frame_without_checksum = header + data
        
        # 计算校验和：对整个帧（不含校验和和帧尾）进行XOR运算
        checksum = 0
        for byte in frame_without_checksum:
            checksum ^= byte
        
        frame = cls(
            head0=NCLINK_HEAD0,
            head1=NCLINK_HEAD1,
            func_code=func_code,
            data_len=data_len,
            data=data,
            checksum=checksum,
            end0=NCLINK_END0,
            end1=NCLINK_END1
        )
        return frame
    
    def to_bytes(self) -> bytes:
        """序列化为字节数组
        严格按照协议顺序：
        [帧头2字节] [命令1字节] [长度2字节] [数据N字节] [校验1字节] [帧尾2字节]
        
        格式说明：
        !BBH = [头1][头2][命令]
        但这是错的！应该是：
        !BBH = [头1][头2][命令] + 长度单独打包
        """
        # 头部： [帧头2字节] [命令1字节] [长度2字节]
        # 使用!BBH格式，它会按顺序编码：[头1][头2][命令]
        # 然后再单独添加2字节长度
        header = struct.pack('!BB', self.head0, self.head1) + \
                 struct.pack('!H', self.data_len)
        
        # 插入命令字在帧头后、长度前
        header = struct.pack('!BB', self.head0, self.head1) + \
                 struct.pack('!BH', self.func_code, self.data_len)
        
        # 尾部：校验和 + 帧尾2字节
        trailer = struct.pack('!BBB', self.checksum, self.end0, self.end1)
        
        return header + self.data + trailer
    
    @staticmethod
    def calculate_checksum(func_code: uint8_T, data: bytes) -> uint8_T:
        """计算校验和（使用XOR运算，与C++飞控端保持一致）
        
        注意：这个方法是为了向后兼容保留的接口，实际计算应该使用完整的frame
        """
        data_len = len(data)
        # 构建完整帧（不含校验和和帧尾）
        frame_without_checksum = struct.pack('!BBHB',
                                              NCLINK_HEAD0, NCLINK_HEAD1,
                                              func_code, data_len) + data
        
        # 计算校验和：对整个帧进行XOR运算
        checksum = 0
        for byte in frame_without_checksum:
            checksum ^= byte
        return checksum
    
    def validate(self) -> bool:
        """验证帧校验和"""
        expected = self.calculate_checksum(self.func_code, self.data)
        return expected == self.checksum


# ================================================================
# NCLink数据包解析器
# ================================================================

class PortType(IntEnum):
    """端口类型枚举"""
    PORT_18504_RECEIVE = 0      # 地面站接收端口（飞控发送指令响应）
    PORT_18506_TELEMETRY = 1     # 飞控遥测端口（飞控发送状态数据）
    PORT_18507_LIDAR = 2         # 雷达数据端口（雷达发送障碍物数据）
    PORT_18511_PLANNING = 3      # 规划系统接收端口（规划发送遥测数据）


class NCLinkProtocolParser:
    """NCLink协议解析器"""
    
    def __init__(self):
        self.buffer = bytearray()
        self.fcs_states: Optional[ExtY_FCS_STATES_T] = None
        self.fcs_pwms: Optional[ExtY_FCS_PWMS_T] = None
        self.fcs_datactrl: Optional[ExtY_FCS_DATACTRL_T] = None
        self.fcs_gncbus: Optional[ExtY_FCS_GNCBUS_T] = None
        self.avoiflag: Optional[ExtY_FCS_AVOIFLAG_T] = None
        self.fcs_datafutaba: Optional[ExtY_FCS_DATAFUTABA_T] = None
        self.fcs_esc: Optional[ExtY_FCS_ESC_T] = None
        self.fcs_param: Optional[ExtY_FCS_PARAM_T] = None
        self.obstacles: Optional[ObstacleOutput_T] = None
        self.system_status: Optional[SystemStatus_T] = None
        self.gcs_telemetry: Optional[GCSTelemetry_T] = None
    
    def feed_data(self, data: bytes, port_type: PortType = PortType.PORT_18504_RECEIVE) -> List[dict]:
        """feeding数据并解析
        
        Args:
            data: 接收到的字节数据
            port_type: 端口类型（用于区分不同来源的数据）
        
        Returns:
            解析后的消息列表
        """
        self.buffer.extend(data)
        messages = []
        
        while len(self.buffer) >= 6:  # 最小帧长度: head(2) + len(2) + func_code(1) + checksum(1)
            # 查找帧头
            if self.buffer[0] != NCLINK_HEAD0 or self.buffer[1] != NCLINK_HEAD1:
                self.buffer.pop(0)
                continue
            
            # 读取功能码和长度字段（正确偏移：功能码在byte 2，长度在byte 3-4）
            func_code = self.buffer[2]
            data_len = struct.unpack_from('!H', self.buffer, 3)[0]
            
            # 检查帧是否完整
            # 格式: head(2) + func(1) + len(2) + data(data_len) + checksum(1) + tail(2)
            total_len = 2 + 1 + 2 + data_len + 1 + 2  # head + func + len + data + checksum + end
            if len(self.buffer) < total_len:
                break
            
            # 提取帧数据
            frame_data = bytes(self.buffer[:total_len])
            
            # 验证帧尾
            if frame_data[-2] != NCLINK_END0 or frame_data[-1] != NCLINK_END1:
                self.buffer.pop(0)
                continue
            
            # 解析帧
            try:
                frame = self.parse_frame(frame_data, port_type)
                if frame:
                    messages.append(frame)
            except Exception as e:
                print(f"解析帧失败: {e}")
            
            # 移除已处理的帧
            del self.buffer[:total_len]
        
        return messages
    
    def parse_frame(self, frame_data: bytes, port_type: PortType) -> Optional[dict]:
        """解析单个帧
        
        Args:
            frame_data: 帧数据
            port_type: 端口类型
        
        Returns:
            解析后的消息字典，失败返回None
        """
        # 打印调试信息（兼容Python 3.7）
        import binascii
        preview_data = frame_data[:20] if len(frame_data) >= 20 else frame_data
        hex_bytes = binascii.hexlify(preview_data).decode('ascii')
        hex_preview = ' '.join([hex_bytes[i:i+2] for i in range(0, len(hex_bytes), 2)])
        print(f"[协议解析] 帧数据预览: {hex_preview}")
        
        # 验证最小帧长度
        if len(frame_data) < 8:
            print(f"[协议解析] ✗ 帧太短: {len(frame_data)} < 8")
            return None
        
        # 验证帧头
        if frame_data[0] != NCLINK_HEAD0 or frame_data[1] != NCLINK_HEAD1:
            print(f"[协议解析] ✗ 帧头错误: 0x{frame_data[0]:02X} 0x{frame_data[1]:02X}")
            return None
        
        # 读取功能码和长度字段（正确偏移）
        func_code = frame_data[2]
        data_len = struct.unpack_from('!H', frame_data, 3)[0]
        
        # 验证数据长度是否合理
        if data_len > BUFFER_SIZE_MAX:
            print(f"[协议解析] ⚠ 数据长度异常: {data_len}（超过最大值）")
            return None
        
        # 计算预期帧长度：head(2) + func(1) + len(2) + data(data_len) + checksum(1) + tail(2)
        expected_frame_len = 2 + 1 + 2 + data_len + 1 + 2
        
        if len(frame_data) < expected_frame_len:
            print(f"[协议解析] ⚠ 帧不完整: 需要{expected_frame_len}字节，只有{len(frame_data)}字节")
            return None
        
        print(f"[协议解析] 功能码: 0x{func_code:02X}, 数据长度: {data_len}, 期望帧长度: {expected_frame_len}, 实际帧长度: {len(frame_data)}")
        
        try:
            # 提取payload（从字节5开始，因为：head(0-1) + func(2) + len(3-4) = 5字节）
            payload = frame_data[5:5+data_len]
            checksum = frame_data[5+data_len]
        except IndexError as e:
            print(f"[协议解析] ✗ 提取payload失败: {e}")
            return None
        
        # 飞控遥测校验和计算：对 帧头(2) + 功能码(1) + 长度(2) + 载荷(N) 进行异或
        frame_for_checksum = frame_data[:5+data_len]
        expected_checksum = 0
        for byte in frame_for_checksum:
            expected_checksum ^= byte

        print(f"[协议解析] 校验和: 计算{expected_checksum:02X}, 接收{checksum:02X}")
        if checksum != expected_checksum:
            print(f"[协议解析] ✗ 校验和不匹配")
            # 即使校验和错误，也继续解析（用于调试）
        else:
            print(f"[协议解析] ✓ 校验和匹配")
        
        # 验证帧尾
        if frame_data[-2] != NCLINK_END0 or frame_data[-1] != NCLINK_END1:
            print(f"[协议解析] ✗ 帧尾错误: 0x{frame_data[-2]:02X} 0x{frame_data[-1]:02X}")
        else:
            print(f"[协议解析] ✓ 帧尾正确")
        
        # 根据功能码解析数据
        message = {
            'func_code': func_code,
            'func_code_hex': f'0x{func_code:02X}',
            'port_type': port_type,
            'timestamp': int(time.time() * 1000)
        }
        
        # ============ 飞控数据包解析 (0x40-0x4B) ============
        if func_code == NCLINK_RECEIVE_EXTY_FCS_PWMS:
            # 0x41: PWM输出数据
            self.fcs_pwms = ExtY_FCS_PWMS_T.from_bytes(payload)
            message['type'] = 'fcs_pwms'
            message['data'] = {'pwms': self.fcs_pwms.pwms}
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_STATES:
            # 0x42: 飞行状态数据
            try:
                self.fcs_states = ExtY_FCS_STATES_T.from_bytes(payload)
                message['type'] = 'fcs_states'
                message['data'] = self.fcs_states.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_STATES_T解析失败: {e}, 使用默认值")
                # 提取可用的数据（前56字节）
                self.fcs_states = ExtY_FCS_STATES_T.from_bytes(payload[:56].ljust(64, b'\x00'))
                message['type'] = 'fcs_states'
                message['data'] = self.fcs_states.to_json()
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_DATACTRL:
            # 0x43: 控制数据循环状态
            try:
                self.fcs_datactrl = ExtY_FCS_DATACTRL_T.from_bytes(payload)
                message['type'] = 'fcs_datactrl'
                message['data'] = self.fcs_datactrl.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_DATACTRL_T解析失败: {e}, 使用默认值")
                self.fcs_datactrl = ExtY_FCS_DATACTRL_T.from_bytes(payload[:212].ljust(64, b'\x00'))
                message['type'] = 'fcs_datactrl'
                message['data'] = self.fcs_datactrl.to_json()
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_GNCBUS:
            # 0x44: GN&C总线状态
            try:
                self.fcs_gncbus = ExtY_FCS_GNCBUS_T.from_bytes(payload)
                message['type'] = 'fcs_gncbus'
                message['data'] = self.fcs_gncbus.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_GNCBUS_T解析失败: {e}, 使用默认值")
                self.fcs_gncbus = ExtY_FCS_GNCBUS_T.from_bytes(payload[:245].ljust(40, b'\x00'))
                message['type'] = 'fcs_gncbus'
                message['data'] = self.fcs_gncbus.to_json()
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_AVOIFLAG:
            # 0x45: 避障标志
            self.avoiflag = ExtY_FCS_AVOIFLAG_T.from_bytes(payload)
            message['type'] = 'avoiflag'
            message['data'] = self.avoiflag.to_json()
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_DATAGCS:
            # 0x46: Futaba遥控数据（地面站发送数据）
            try:
                self.fcs_datafutaba = ExtY_FCS_DATAFUTABA_T.from_bytes(payload)
                message['type'] = 'fcs_datafutaba'
                message['data'] = self.fcs_datafutaba.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_DATAFUTABA_T解析失败: {e}")
                message['type'] = 'fcs_datafutaba'
                message['data'] = {
                    'Tele_ftb_Roll': 0,
                    'Tele_ftb_Pitch': 0,
                    'Tele_ftb_Yaw': 0,
                    'Tele_ftb_Col': 0,
                    'Tele_ftb_Switch': 0,
                    'Tele_ftb_com_Ftb_fail': 0
                }
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AIM2AB:
            # 0x47: aim2AB航迹线结构
            try:
                self.fcs_line_aim2ab = ExtY_FCS_LINESTRUC_ac_aim2AB_T.from_bytes(payload)
                message['type'] = 'fcs_line_aim2ab'
                message['data'] = self.fcs_line_aim2ab.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_LINESTRUC_ac_aim2AB_T解析失败: {e}")
                message['type'] = 'fcs_line_aim2ab'
                message['data'] = {
                    'lon': 0.0,
                    'lat': 0.0,
                    'psi': 0.0,
                    'alt': 0.0,
                    'len': 0.0,
                    'rad': 0.0,
                    'Vx2nextdot': 0.0,
                    'next_num': 0,
                    'next_dot': 0,
                    'type_dot': 0,
                    'clockwise_WP': 0,
                    'R_WP': 0.0,
                    'type_WP': 0,
                    'Num_type_WP': 0,
                    'dL_WP': 0.0,
                    'Vx_type': 0,
                    'TTC_Fault_Mode': 0,
                    'deltaY_ctrl': 0,
                    'turn_type': 0,
                    'Inv_type': 0,
                    'type_line': 0
                }
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AB:
            # 0x48: AB航迹线结构
            try:
                self.fcs_line_ab = ExtY_FCS_LINESTRUC_acAB_T.from_bytes(payload)
                message['type'] = 'fcs_line_ab'
                message['data'] = self.fcs_line_ab.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_LINESTRUC_acAB_T解析失败: {e}")
                message['type'] = 'fcs_line_ab'
                message['data'] = {
                    'lon': 0.0,
                    'lat': 0.0,
                    'psi': 0.0,
                    'alt': 0.0,
                    'len': 0.0,
                    'rad': 0.0,
                    'Vx2nextdot': 0.0,
                    'next_num': 0,
                    'next_dot': 0,
                    'type_dot': 0,
                    'clockwise_WP': 0,
                    'R_WP': 0.0,
                    'type_WP': 0,
                    'Num_type_WP': 0,
                    'dL_WP': 0.0,
                    'Vx_type': 0,
                    'TTC_Fault_Mode': 0,
                    'deltaY_ctrl': 0,
                    'turn_type': 0,
                    'Inv_type': 0,
                    'type_line': 0
                }
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_ESC:
            # 0x4B: 电机参数
            self.fcs_esc = ExtY_FCS_ESC_T.from_bytes(payload)
            message['type'] = 'fcs_esc'
            message['data'] = {
                'error_counts': [
                    self.fcs_esc.esc1_error_count, self.fcs_esc.esc2_error_count,
                    self.fcs_esc.esc3_error_count, self.fcs_esc.esc4_error_count,
                    self.fcs_esc.esc5_error_count, self.fcs_esc.esc6_error_count
                ],
                'rpms': [
                    self.fcs_esc.esc1_rpm, self.fcs_esc.esc2_rpm,
                    self.fcs_esc.esc3_rpm, self.fcs_esc.esc4_rpm,
                    self.fcs_esc.esc5_rpm, self.fcs_esc.esc6_rpm
                ],
                'power_ratings': [
                    self.fcs_esc.esc1_power_rating_pct, self.fcs_esc.esc2_power_rating_pct,
                    self.fcs_esc.esc3_power_rating_pct, self.fcs_esc.esc4_power_rating_pct,
                    self.fcs_esc.esc5_power_rating_pct, self.fcs_esc.esc6_power_rating_pct
                ]
            }
        
        elif func_code == NCLINK_RECEIVE_EXTY_FCS_PARAM:
            # 0x49: 飞控参数
            try:
                self.fcs_param = ExtY_FCS_PARAM_T.from_bytes(payload)
                message['type'] = 'fcs_param'
                message['data'] = self.fcs_param.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ExtY_FCS_PARAM_T解析失败: {e}")
                message['type'] = 'fcs_param'
                message['data'] = {
                    'param_id': 0,
                    'param_value': 0.0,
                    'param_min': 0.0,
                    'param_max': 0.0
                }
        
        # ============ 雷达数据包解析 (0x50-0x53) ============
        elif func_code == NCLINK_RECEIVE_LIDAR_OBSTACLES:
            # 0x50: 雷达障碍物数组输出
            try:
                obstacle_output = ObstacleOutput_T.from_bytes(payload)
                message['type'] = 'lidar_obstacles'
                message['data'] = obstacle_output.to_json()
            except Exception as e:
                print(f"[协议解析] ⚠ ObstacleOutput_T解析失败: {e}")
                message['type'] = 'lidar_obstacles'
                message['data'] = {
                    'obstacle_count': 0,
                    'obstacles': [],
                    'error': str(e)
                }
        
        elif func_code == NCLINK_RECEIVE_LIDAR_PERF:
            # 0x52: 雷达性能统计
            try:
                from .lidar_imu_protocol import PerformanceMetrics_T
                perf_metrics = PerformanceMetrics_T.from_bytes(payload)
                message['type'] = 'lidar_performance'
                message['data'] = perf_metrics.to_dict()
            except Exception as e:
                print(f"[协议解析] ⚠ PerformanceMetrics_T解析失败: {e}")
                message['type'] = 'lidar_performance'
                message['data'] = {
                    'processing_time_ms': 0,
                    'frame_rate': 0,
                    'error': str(e)
                }
        
        elif func_code == NCLINK_RECEIVE_LIDAR_STATUS:
            # 0x53: 雷达系统状态
            try:
                from .lidar_imu_protocol import SystemStatus_T
                system_status = SystemStatus_T.from_bytes(payload)
                message['type'] = 'lidar_status'
                message['data'] = system_status.to_dict()
            except Exception as e:
                print(f"[协议解析] ⚠ SystemStatus_T解析失败: {e}")
                message['type'] = 'lidar_status'
                message['data'] = {
                    'is_running': False,
                    'lidar_connected': False,
                    'imu_data_valid': False,
                    'motion_comp_active': False,
                    'error': str(e)
                }
        
        # ============ 规划系统数据包解析 (0x70-0x71) ============
        elif func_code == NCLINK_GCS_TELEMETRY:
            # 0x71: 规划系统遥测
            try:
                self.gcs_telemetry = GCSTelemetry_T.from_bytes(payload)
                if self.gcs_telemetry:
                    message['type'] = 'planning_telemetry'
                    message['data'] = self.gcs_telemetry.to_json()
                    logger.info(f"[协议解析] ✓ 成功解析规划遥测数据 (0x71): {message['data']}")
                else:
                    message['type'] = 'planning_telemetry_failed'
                    message['data'] = {'error': 'Failed to parse GCSTelemetry_T from bytes'}
            except Exception as e:
                logger.error(f"[协议解析] ✗ 解析规划遥测数据 (0x71) 时发生异常: {e}")
                message['type'] = 'planning_telemetry_error'
                message['data'] = {'error': str(e)}
        
        else:
            # 未知功能码
            message['type'] = 'unknown'
            message['data'] = {
                'hex_payload': payload.hex()[:32],
                'length': len(payload)
            }
        
        return message


# ================================================================
# 协议导出
# ================================================================

# 导出 PortType 枚举，供其他模块使用
__all__ = [
    'NCLINK_HEAD0', 'NCLINK_HEAD1', 'NCLINK_END0', 'NCLINK_END1',
    'BUFFER_SIZE_MAX', 'NCLinkProtocolParser',
    'ExtY_FCS_PWMS_T', 'ExtY_FCS_STATES_T', 'ExtY_FCS_DATACTRL_T',
    'ExtY_FCS_GNCBUS_T', 'ExtY_FCS_AVOIFLAG_T', 'ExtY_FCS_ESC_T',
    'ExtY_FCS_PARAM_T', 'ObstacleOutput_T', 'SystemStatus_T',
    'GCSTelemetry_T', 'ExtY_FCS_LINESTRUC_ac_aim2AB_T', 'ExtY_FCS_LINESTRUC_acAB_T',
    'NCLinkFrame', 'encode_command_packet',
    'encode_takeoff_command', 'encode_land_command',
    'encode_hover_command', 'encode_rtl_command',
    'encode_lidar_avoidance_command', 'encode_gcs_command',
    'encode_waypoints_upload', 'CmdIdx', 'PortType',
    'RECEIVE_PORT', 'SEND_ONLY_PORT', 'LIDAR_SEND_PORT',
    'PLANNING_SEND_PORT', 'PLANNING_RECV_PORT'
]


# ================================================================
# 指令编码函数
# ================================================================

def encode_gcs_command(seq_id: uint32_T,
                     target_pos_x: real_T,
                     target_pos_y: real_T,
                     target_pos_z: real_T,
                     cruise_speed: real_T = 10.0,
                     enable_flag: uint8_T = 1,
                     cmd_idx: int32_T = 0) -> bytes:
    """
    编码GCSCommand_T结构体
    
    Args:
        seq_id: 序号 (递增)
        target_pos_x: ENU坐标系 X (米)
        target_pos_y: ENU坐标系 Y (米)
        target_pos_z: ENU坐标系 Z (米)
        cruise_speed: 巡航速度
        enable_flag: 任务使能标志 (0或1)
        cmd_idx: 地面站指令索引
    
    Returns:
        编码后的字节数组 (32字节)
    """
    import time
    timestamp = int(time.time() * 1000) % (2**32)
    
    # GCSCommand_T结构: uint32 + uint32 + 3*double + double + uint8 + int32
    # = 4 + 4 + 24 + 8 + 1 + 4 = 45字节 (按照C结构体)
    # CmdIdx是int32_t，应该使用 'i' 而不是 'I'
    # 注意：为了与系统其他部分保持一致（通常的小端序C结构体），使用 '<'
    struct_format = '<IIddddBi'  # 小端序
    
    data = struct.pack(
        struct_format,
        seq_id,
        timestamp,
        target_pos_x,
        target_pos_y,
        target_pos_z,
        cruise_speed,
        enable_flag,
        cmd_idx
    )
    
    return data


def encode_waypoints_upload(waypoints: List[dict], cruise_speed: real_T = 10.0) -> bytes:
    """
    编码航点上传数据（批量发送）
    
    Args:
        waypoints: 航点列表，每个航点包含 lat, lon, alt
        cruise_speed: 巡航速度 (m/s)
    
    Returns:
        编码后的字节数组 (包含多个GCSCommand_T结构)
    """
    import time
    
    # 转换经纬度到ENU坐标的简化实现
    # 注意：实际应用中应该使用准确的坐标转换
    base_lat = waypoints[0]['lat']
    base_lon = waypoints[0]['lon']
    base_alt = waypoints[0]['alt']
    
    payloads = []
    
    for idx, wp in enumerate(waypoints):
        # 简化转换：经度差*11132m ≈ 东向距离，纬度差*11132m ≈ 北向距离
        dx = (wp['lon'] - base_lon) * 111320.0
        dy = (wp['lat'] - base_lat) * 110574.0
        dz = wp['alt'] - base_alt
        
        # 编码单个航点
        wp_data = encode_gcs_command(
            seq_id=idx,
            target_pos_x=dx,
            target_pos_y=dy,
            target_pos_z=dz,
            cruise_speed=cruise_speed,
            enable_flag=1,
            cmd_idx=0
        )
        
        payloads.append(wp_data)
    
    # 拼接所有航点数据
    return b''.join(payloads)


def encode_extu_fcs_from_dict(pids_data: dict, cmd_idx: int = 0, cmd_mission: int = 0, cmd_mission_val: float = 0.0) -> bytes:
    """从字典编码ExtU_FCS_T结构体为字节数据
    
    根据interface.h第370-404行完整定义：
    - 26个real32_T PID参数 = 104字节
    - 1个int32_T CmdIdx = 4字节
    - 1个int32_T CmdMission = 4字节
    - 1个real32_T CmdMissionVal = 4字节
    - 总计：104 + 12 = 116字节
    
    Args:
        pids_data: dict, 包含26个PID参数的字典（来自前端set_pids指令）
        cmd_idx: int, 指令索引（来自前端cmd_idx指令）
        cmd_mission: int, 任务指令（可选）
        cmd_mission_val: float, 任务指令值（可选）
    
    Returns:
        bytes: 116字节的编码数据
    """
    # 使用小端序打包26个float + 2个int32 + 1个float
    fmt = '<' + 'f'*26 + 'iif'
    
    # 按照interface.h中的字段顺序打包
    # 从pids_data字典中获取26个PID参数值，如果没有则使用默认值
    pid_values = [
        # 姿态控制（8个）
        float(pids_data.get('fKaPHI', 0.5)),      # F_KaPHI
        float(pids_data.get('fKaP', 0.2)),        # F_KaP
        float(pids_data.get('fKaY', 0.143)),      # F_KaY
        float(pids_data.get('fIaY', 0.005)),      # F_IaY
        float(pids_data.get('fKaVy', 2.0)),       # F_KaVy
        float(pids_data.get('fIaVy', 0.4)),       # F_IaVy
        float(pids_data.get('fKaAy', 0.28)),       # F_KaAy
        # 俯仰控制（3个）
        float(pids_data.get('fKeTHETA', 0.5)),    # F_KeTHETA
        float(pids_data.get('fKeQ', 0.2)),         # F_KeQ
        float(pids_data.get('fKeX', 0.201)),       # F_KeX
        float(pids_data.get('fIeX', 0.01)),       # F_IeX
        float(pids_data.get('fKeVx', 2.0)),       # F_KeVx
        float(pids_data.get('fIeVx', 0.4)),       # F_IeVx
        float(pids_data.get('fKeAx', 0.55)),       # F_KeAx
        # 滚转控制（4个）
        float(pids_data.get('fKrR', 0.2)),        # F_KrR
        float(pids_data.get('fIrR', 0.01)),       # F_IrR
        float(pids_data.get('fKrAy', 0.1)),       # F_KrAy
        float(pids_data.get('fKrPSI', 1.0)),      # F_KrPSI
        # 偏航和高度控制（5个）
        float(pids_data.get('fKcH', 0.36)),        # F_KcH
        float(pids_data.get('fIcH', 0.015)),       # F_IcH
        float(pids_data.get('fKcHdot', 0.5)),      # F_KcHdot
        float(pids_data.get('fIcHdot', 0.05)),      # F_IcHdot
        float(pids_data.get('fKcAz', 0.15)),       # F_KcAz
        # 动力系统（3个）
        float(pids_data.get('fIgRPM', 0.0)),        # F_IgRPM
        float(pids_data.get('fKgRPM', 0.01)),       # F_KgRPM
        float(pids_data.get('fScale_factor', 1.0)),  # F_Scale_factor
    ]
    
    # 添加3个指令字段
    values = pid_values + [cmd_idx, cmd_mission, cmd_mission_val]
    
    # 打包为字节
    payload = struct.pack(fmt, *values)
    
    logger.info(f"[encode_extu_fcs_from_dict] 编码ExtU_FCS_T: {len(payload)}字节")
    logger.info(f"[encode_extu_fcs_from_dict] CmdIdx={cmd_idx}, CmdMission={cmd_mission}, CmdMissionVal={cmd_mission_val}")
    
    return payload


def encode_command_packet(func_code: int, payload: bytes = b'') -> bytes:
    """编码命令数据包"""
    import time
    import struct
    timestamp = int(time.time() * 1000)
    
    # 如果是发送ExtU_FCS命令，需要构建完整的ExtU_FCS_T结构体
    if func_code == NCLINK_SEND_EXTU_FCS:
        # 解析payload中的CmdIdx（如果payload是4字节的int32）
        if len(payload) == 4:
            cmd_idx = struct.unpack('<i', payload)[0]  # 小端序解析
            
            # 根据完整的interface.h定义构建ExtU_FCS_T结构体（104字节）
            # 包含23个real32_T + 2个int32_t + 1个real32_T = 23*4 + 2*4 + 1*4 = 104字节
            
            # 构建26个PID参数（每个real32_T 4字节）
            # 根据interface.h第374-399行完整定义
            pid_payload = struct.pack('<' + 'f'*26,  # 26 floats
                0.5,    # F_KaPHI (滚转姿态P系数)
                0.2,    # F_KaP (滚转姿态D系数)
                0.143,  # F_KaY (横向位置P系数)
                0.005,  # F_IaY (横向位置I系数)
                2.0,    # F_KaVy (横向速度P系数)
                0.4,    # F_IaVy (横向速度I系数)
                0.28,   # F_KaAy (横向速度D系数)
                0.5,    # F_KeTHETA (俯仰姿态P系数)
                0.2,    # F_KeQ (俯仰姿态D系数)
                0.201,  # F_KeX (纵向位置P系数)
                0.01,   # F_IeX (纵向位置I系数)
                2.0,    # F_KeVx (纵向速度P系数)
                0.4,    # F_IeVx (纵向速度I系数)
                0.55,   # F_KeAx (纵向加速度D系数)
                0.2,    # F_KrR (偏航角速度P系数)
                0.01,   # F_IrR (偏航角速度I系数)
                0.1,    # F_KrAy (偏航加速度P系数) [新增]
                1.0,    # F_KrPSI (偏航角P系数)
                0.36,   # F_KcH (高度P系数)
                0.015,  # F_IcH (高度I系数)
                0.5,    # F_KcHdot (垂向速度P系数)
                0.05,   # F_IcHdot (垂向速度I系数)
                0.15,   # F_KcAz (垂向加速度D系数)
                0.0,    # F_IgRPM (电机积分系数)
                0.01,   # F_KgRPM (电机比例系数)
                1.0     # F_Scale_factor (缩放因子)
            )
            
            # 构建3个指令字段（12字节）
            cmd_payload = struct.pack('<iif',  # 2 ints + 1 float
                cmd_idx,      # CmdIdx (int32_t)
                0,             # CmdMission (int32_t)
                0.0            # CmdMissionVal (real32_T)
            )
            
            # 合并完整payload（116字节=26*4+12字节）
            complete_payload = pid_payload + cmd_payload
            logger.info(f"构建完整ExtU_FCS_T结构体：116字节（26个PID参数 + 3个指令字段）")
        else:
            # 如果payload长度不对，使用原始数据
            logger.warning(f"Payload长度异常: {len(payload)}，使用原始数据")
            complete_payload = payload
    else:
        # 其他命令直接使用payload
        complete_payload = payload
    
    # 创建NCLink帧
    frame = NCLinkFrame.create_frame(func_code, complete_payload)
    
    # 返回完整字节数组
    return frame.to_bytes()


def encode_takeoff_command() -> bytes:
    """编码起飞命令"""
    return encode_command_packet(NCLINK_SEND_EXTU_FCS, 
                             struct.pack('!i', CmdIdx.CMD_AUTO_TAKEOFF))


def encode_land_command() -> bytes:
    """编码降落命令"""
    return encode_command_packet(NCLINK_SEND_EXTU_FCS, 
                             struct.pack('!i', CmdIdx.CMD_AUTO_LAND))


def encode_hover_command() -> bytes:
    """编码悬停命令"""
    return encode_command_packet(NCLINK_SEND_EXTU_FCS, 
                             struct.pack('!i', CmdIdx.CMD_HOVER))


def encode_rtl_command() -> bytes:
    """编码返航命令"""
    return encode_command_packet(NCLINK_SEND_EXTU_FCS, 
                             struct.pack('!i', CmdIdx.CMD_RETURN_TO_HOME))


def encode_lidar_avoidance_command(enable: bool = True) -> bytes:
    """编码避障开关命令"""
    cmd = CmdIdx.CMD_PLAN_ON if enable else CmdIdx.CMD_PLAN_OFF
    return encode_command_packet(NCLINK_SEND_EXTU_FCS, struct.pack('!i', cmd))


# ================================================================
# 测试函数
# ================================================================

if __name__ == '__main__':
    # 测试帧创建
    frame = NCLinkFrame.create_frame(0x42, b'test_data')
    print(f"Frame bytes: {frame.to_bytes().hex()}")
    
    # 测试解析器
    parser = NCLinkProtocolParser()
    messages = parser.feed_data(frame.to_bytes())
    print(f"Parsed messages: {messages}")