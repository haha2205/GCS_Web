"""
CSV数据记录辅助函数（完整版）
基于interface.h中完整的ExtY_FCS_T结构体定义
实现"宽表"格式的CSV记录（不带category列）
总列数：225列（重新核对后）
"""

from typing import Dict, Any
from datetime import datetime


# ==================== 列数常量 ====================

# 总列数（重新核对）
TOTAL_COLUMNS = 230  # 225 -AIM(1) -AB(1) +GCS(7) = 230

# 各数据段的列数（根据interface.h严格计数）
COL_TIMESTAMP = 1
COL_PWMS = 8
COL_STATES = 12
COL_DATACTRL = 53
COL_GNCBUS = 75
COL_AVOIFLAG = 3
COL_FUTABA = 6
COL_GCS = 11
COL_AC_AIM2AB = 21  # Corrected from 22
COL_AC_AB = 21      # Corrected from 22
COL_PARAM = 1
COL_ESC = 18

# 累计偏移量
OFFSET_PWMS = COL_TIMESTAMP
OFFSET_STATES = OFFSET_PWMS + COL_PWMS
OFFSET_DATACTRL = OFFSET_STATES + COL_STATES
OFFSET_GNCBUS = OFFSET_DATACTRL + COL_DATACTRL
OFFSET_AVOIFLAG = OFFSET_GNCBUS + COL_GNCBUS
OFFSET_FUTABA = OFFSET_AVOIFLAG + COL_AVOIFLAG
OFFSET_GCS = OFFSET_FUTABA + COL_FUTABA
OFFSET_AC_AIM2AB = OFFSET_GCS + COL_GCS
OFFSET_AC_AB = OFFSET_AC_AIM2AB + COL_AC_AIM2AB
OFFSET_PARAM = OFFSET_AC_AB + COL_AC_AB
OFFSET_ESC = OFFSET_PARAM + COL_PARAM

# 验证总数
# 1 + 8 + 12 + 53 + 75 + 3 + 6 + 4 + 22 + 22 + 1 + 18 = 225 ✓


# ==================== 辅助函数 ====================

def _safe_float(value, default=0.0):
    """安全转换为float"""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _safe_int(value, default=0):
    """安全转换为int"""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

def _safe_str(value, default=""):
    """安全转换为str"""
    try:
        if value is None:
            return default
        return str(value)
    except (TypeError, ValueError):
        return default


# ==================== 表头定义 ====================

def get_full_header() -> str:
    """
    获取完整的CSV表头（所有字段展开）
    格式：timestamp,pwm1,pwm2,...,states_lat,states_lon,...
    """
    header_fields = []
    
    # 1. 时间戳
    header_fields.append("timestamp")
    
    # 2. PWMS数据 (8个字段)
    for i in range(1, 9):
        header_fields.append(f"pwm{i}")
    
    # 3. STATES数据 (12个字段)
    header_fields.extend([
        "states_lat", "states_lon", "states_height",
        "states_Vx_GS", "states_Vy_GS", "states_Vz_GS",
        "states_p", "states_q", "states_r",
        "states_phi", "states_theta", "states_psi"
    ])
    
    # 4. DATACTRL数据 (53个字段)
    # ailOutLoop (8)
    header_fields.extend([
        "dataCtrl_n_ailOutLoop_dY_delta",
        "dataCtrl_n_ailOutLoop_Vy_dY2Vy",
        "dataCtrl_n_ailOutLoop_Vy_var",
        "dataCtrl_n_ailOutLoop_Vy_delta",
        "dataCtrl_n_ailOutLoop_Vy_P",
        "dataCtrl_n_ailOutLoop_Vy_Int",
        "dataCtrl_n_ailOutLoop_Vy_D",
        "dataCtrl_n_ailOutLoop_ail_ffc"
    ])
    # ailInLoop (8)
    header_fields.extend([
        "dataCtrl_n_ailInLoop_ail_trim",
        "dataCtrl_n_ailInLoop_phi_trim",
        "dataCtrl_n_ailInLoop_phi_var",
        "dataCtrl_n_ailInLoop_delta_phi",
        "dataCtrl_n_ailInLoop_phi_P",
        "dataCtrl_n_ailInLoop_phi_D",
        "dataCtrl_n_ailInLoop_ail_fbc",
        "dataCtrl_n_ailInLoop_ail_law_out"
    ])
    # eleOutLoop (8)
    header_fields.extend([
        "dataCtrl_n_eleOutLoop_dX_delta",
        "dataCtrl_n_eleOutLoop_Vx_dX2Vx",
        "dataCtrl_n_eleOutLoop_Vx_var",
        "dataCtrl_n_eleOutLoop_Vx_delta",
        "dataCtrl_n_eleOutLoop_Vx_P",
        "dataCtrl_n_eleOutLoop_Vx_Int",
        "dataCtrl_n_eleOutLoop_Vx_D",
        "dataCtrl_n_eleOutLoop_ele_ffc"
    ])
    # EleInLoop (8)
    header_fields.extend([
        "dataCtrl_n_EleInLoop_theta_trim",
        "dataCtrl_n_EleInLoop_ele_trim",
        "dataCtrl_n_EleInLoop_theta_var",
        "dataCtrl_n_EleInLoop_delta_theta",
        "dataCtrl_n_EleInLoop_theta_P",
        "dataCtrl_n_EleInLoop_theta_D",
        "dataCtrl_n_EleInLoop_ele_fbc",
        "dataCtrl_n_EleInLoop_ele_law_out"
    ])
    # RudOutLoop (3)
    header_fields.extend([
        "dataCtrl_n_RudOutLoop_psi_dy",
        "dataCtrl_n_RudOutLoop_psi_delta",
        "dataCtrl_n_RudOutLoop_R_dPsi2R"
    ])
    # rudInLoop (7)
    header_fields.extend([
        "dataCtrl_n_rudInLoop_rud_trim",
        "dataCtrl_n_rudInLoop_R_var",
        "dataCtrl_n_rudInLoop_dR_delta",
        "dataCtrl_n_rudInLoop_R_P",
        "dataCtrl_n_rudInLoop_R_Int",
        "dataCtrl_n_rudInLoop_rud_fbc",
        "dataCtrl_n_rudInLoop_rud_law_out"
    ])
    # colOutLoop (8)
    header_fields.extend([
        "dataCtrl_n_colOutLoop_H_delta",
        "dataCtrl_n_colOutLoop_Hdot_dH2Vz",
        "dataCtrl_n_colOutLoop_Hdot_var",
        "dataCtrl_n_colOutLoop_Hdot_delta",
        "dataCtrl_n_colOutLoop_Hdot_P",
        "dataCtrl_n_colOutLoop_Hdot_Int",
        "dataCtrl_n_colOutLoop_Hdot_D",
        "dataCtrl_n_colOutLoop_col_fbc"
    ])
    # colInLoop (3)
    header_fields.extend([
        "dataCtrl_n_colInLoop_col_Vx",
        "dataCtrl_n_colInLoop_col_law",
        "dataCtrl_n_colInLoop_col_law_out"
    ])
    
    # 5. GNCBUS数据 (75字段)
    # TokenMode (17)
    header_fields.extend([
        "GNCBus_TokenMode_OnSky",
        "GNCBus_TokenMode_Ctrl_Mode",
        "GNCBus_TokenMode_Pre_CMD",
        "GNCBus_TokenMode_rud_state",
        "GNCBus_TokenMode_ail_state",
        "GNCBus_TokenMode_ele_state",
        "GNCBus_TokenMode_col_state",
        "GNCBus_TokenMode_nav_guid",
        "GNCBus_TokenMode_cmd_guid",
        "GNCBus_TokenMode_mode_guid",
        "GNCBus_TokenMode_step_guid",
        "GNCBus_TokenMode_mode_nav",
        "GNCBus_TokenMode_token_nav",
        "GNCBus_TokenMode_step_nav",
        "GNCBus_TokenMode_mode_vert",
        "GNCBus_TokenMode_token_vert",
        "GNCBus_TokenMode_step_vert",
        "GNCBus_TokenMode_mode_horiz",
        "GNCBus_TokenMode_token_horiz"
    ])
    # FtbOpt (10)
    header_fields.extend([
        "GNCBus_FtbOpt_ele_opt",
        "GNCBus_FtbOpt_ail_opt",
        "GNCBus_FtbOpt_rud_opt",
        "GNCBus_FtbOpt_col_opt",
        "GNCBus_FtbOpt_R_opt",
        "GNCBus_FtbOpt_Vx_opt",
        "GNCBus_FtbOpt_Vy_opt",
        "GNCBus_FtbOpt_coldt_opt",
        "GNCBus_FtbOpt_col0_opt",
        "GNCBus_FtbOpt_Ftb_Switch"
    ])
    # SrcValue (2)
    header_fields.extend([
        "GNCBus_SrcValue_ac_SrcCmdV",
        "GNCBus_SrcValue_SrcV_fus"
    ])
    # MixValue (10)
    header_fields.extend([
        "GNCBus_MixValue_col_mix",
        "GNCBus_MixValue_phi_mix",
        "GNCBus_MixValue_Vx_mix",
        "GNCBus_MixValue_dX_mix",
        "GNCBus_MixValue_theta_mix",
        "GNCBus_MixValue_Vy_mix",
        "GNCBus_MixValue_dY_mix",
        "GNCBus_MixValue_psi_mix",
        "GNCBus_MixValue_Hdot_mix",
        "GNCBus_MixValue_height_mix"
    ])
    # CmdValue (7)
    header_fields.extend([
        "GNCBus_CmdValue_phi_cmd",
        "GNCBus_CmdValue_Hdot_cmd",
        "GNCBus_CmdValue_R_cmd",
        "GNCBus_CmdValue_psi_cmd",
        "GNCBus_CmdValue_Vx_cmd",
        "GNCBus_CmdValue_Vy_cmd",
        "GNCBus_CmdValue_height_cmd"
    ])
    # VarValue (4)
    header_fields.extend([
        "GNCBus_VarValue_psi_var",
        "GNCBus_VarValue_height_var",
        "GNCBus_VarValue_dX_var",
        "GNCBus_VarValue_dY_var"
    ])
    # TrimValue (3)
    header_fields.extend([
        "GNCBus_TrimValue_Vx_trim",
        "GNCBus_TrimValue_col_trim",
        "GNCBus_TrimValue_col_autotrim"
    ])
    # ParamsLMT (10)
    header_fields.extend([
        "GNCBus_ParamsLMT_Vx_LMT",
        "GNCBus_ParamsLMT_Vy_LMT",
        "GNCBus_ParamsLMT_R_LMT",
        "GNCBus_ParamsLMT_Hdot_ILmt",
        "GNCBus_ParamsLMT_Hdot_UpLMT",
        "GNCBus_ParamsLMT_Hdot_DownLMT",
        "GNCBus_ParamsLMT_R_FLYTURN",
        "GNCBus_ParamsLMT_R_unit",
        "GNCBus_ParamsLMT_Hdot_unit",
        "GNCBus_ParamsLMT_Vx_unit",
        "GNCBus_ParamsLMT_Vy_unit"
    ])
    # AcValue (4)
    header_fields.extend([
        "GNCBus_AcValue_ac_dY",
        "GNCBus_AcValue_ac_dX",
        "GNCBus_AcValue_ac_dPsi",
        "GNCBus_AcValue_ac_dL"
    ])
    # HoverValue (3)
    header_fields.extend([
        "GNCBus_HoverValue_lon_hov",
        "GNCBus_HoverValue_lat_hov",
        "GNCBus_HoverValue_IsHovStatus_hov"
    ])
    # HomeValue (2)
    header_fields.extend([
        "GNCBus_HomeValue_lon_home",
        "GNCBus_HomeValue_lat_home"
    ])
    
    # 6. AVOIFLAG数据 (3字段)
    header_fields.extend([
        "AvoiFlag_LaserRadar_Enabled",
        "AvoiFlag_AvoidanceFlag",
        "AvoiFlag_GuideFlag"
    ])
    
    # 7. DATAFUTABA数据 (6字段)
    header_fields.extend([
        "Tele_ftb_Roll",
        "Tele_ftb_Pitch",
        "Tele_ftb_Yaw",
        "Tele_ftb_Col",
        "Tele_ftb_Switch",
        "Tele_ftb_com_Ftb_fail"
    ])
    
    # 8. DATAGCS数据 (4字段)
    header_fields.extend([
        "Tele_GCS_CmdIdx",
        "Tele_GCS_Mission",
        "Tele_GCS_Val",
        "Tele_GCS_com_GCS_fail"
    ])
    
    # 9. ac_aim2AB数据 (22字段)
    header_fields.extend([
        "ac_aim2AB_lon", "ac_aim2AB_lat", "ac_aim2AB_psi", "ac_aim2AB_alt",
        "ac_aim2AB_len", "ac_aim2AB_rad", "ac_aim2AB_Vx2nextdot",
        "ac_aim2AB_next_num", "ac_aim2AB_next_dot", "ac_aim2AB_type_dot",
        "ac_aim2AB_clockwise_WP", "ac_aim2AB_R_WP", "ac_aim2AB_type_WP",
        "ac_aim2AB_Num_type_WP", "ac_aim2AB_dL_WP", "ac_aim2AB_Vx_type",
        "ac_aim2AB_TTC_Fault_Mode", "ac_aim2AB_deltaY_ctrl",
        "ac_aim2AB_turn_type", "ac_aim2AB_Inv_type", "ac_aim2AB_type_line"
    ])
    
    # 10. acAB数据 (22字段)
    header_fields.extend([
        "acAB_lon", "acAB_lat", "acAB_psi", "acAB_alt",
        "acAB_len", "acAB_rad", "acAB_Vx2nextdot",
        "acAB_next_num", "acAB_next_dot", "acAB_type_dot",
        "acAB_clockwise_WP", "acAB_R_WP", "acAB_type_WP",
        "acAB_Num_type_WP", "acAB_dL_WP", "acAB_Vx_type",
        "acAB_TTC_Fault_Mode", "acAB_deltaY_ctrl",
        "acAB_turn_type", "acAB_Inv_type", "acAB_type_line"
    ])
    
    # 11. PARAMS数据 (1字段)
    header_fields.append("param_TimeStamp")
    
    # 12. ESC数据 (18字段)
    for i in range(1, 7):
        header_fields.append(f"esc{i}_error_count")
    for i in range(1, 7):
        header_fields.append(f"esc{i}_rpm")
    for i in range(1, 7):
        header_fields.append(f"esc{i}_power_rating_pct")
    
    return ",".join(header_fields)


def get_data_for_type(data_type: str, data: Dict[str, Any]) -> str:
    """
    根据数据类型生成对应的数据行字符串
    
    Args:
        data_type: 数据类型 ('fcs_pwms', 'fcs_states', 'fcs_datactrl', etc.)
        data: 数据字典
    
    Returns:
        CSV格式字符串（总225列）
    """
    try:
        timestamp = _safe_str(data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]))
        telemetry_data = data.get('data', {})
        
        # 根据类型生成数据
        if data_type == 'fcs_pwms':
            return _format_pwms_row(timestamp, telemetry_data)
        elif data_type == 'fcs_states':
            return _format_states_row(timestamp, telemetry_data)
        elif data_type == 'fcs_datactrl':
            return _format_datactrl_row(timestamp, telemetry_data)
        elif data_type == 'fcs_gncbus':
            return _format_gncbus_row(timestamp, telemetry_data)
        elif data_type == 'avoiflag':
            return _format_voiflag_row(timestamp, telemetry_data)
        elif data_type == 'fcs_datafutaba':
            return _format_futaba_row(timestamp, telemetry_data)
        elif data_type == 'planning_telemetry':  # Updated from fcs_datagcs
            return _format_gcs_row(timestamp, telemetry_data)
        elif data_type == 'fcs_line_aim2ab':  # Updated from fcs_ac_aim2ab
            return _format_aim2ab_row(timestamp, telemetry_data)
        elif data_type == 'fcs_line_ab':  # Updated from fcs_ac_ab
            return _format_acab_row(timestamp, telemetry_data)
        elif data_type == 'fcs_param':
            return _format_param_row(timestamp, telemetry_data)
        elif data_type == 'fcs_esc':
            return _format_esc_row(timestamp, telemetry_data)
        else:
            # 未知类型，只返回timestamp
            return timestamp + "," * (TOTAL_COLUMNS - 1)
    except Exception as e:
        # 如果出错，返回timestamp和空列
        timestamp = _safe_str(data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]))
        return timestamp + "," * (TOTAL_COLUMNS - 1)


def _format_pwms_row(timestamp: str, pwms_data: Dict[str, Any]) -> str:
    """格式化PWMS数据行"""
    row = [timestamp]
    
    # PWMS数据 (8列)
    pwms = pwms_data.get('pwms', [0] * 8)
    if not isinstance(pwms, (list, tuple)):
        pwms = [0] * 8
    for i in range(8):
        val = pwms[i] if i < len(pwms) else 0
        row.append(f"{_safe_float(val):.2f}")
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_states_row(timestamp: str, states_data: Dict[str, Any]) -> str:
    """格式化STATES数据行"""
    row = [timestamp]
    
    # PWMS为空 (8列)
    row.extend([""] * COL_PWMS)
    
    # STATES数据 (12列)
    row.append(f"{_safe_float(states_data.get('states_lat')):.8f}")
    row.append(f"{_safe_float(states_data.get('states_lon')):.8f}")
    row.append(f"{_safe_float(states_data.get('states_height')):.3f}")
    row.append(f"{_safe_float(states_data.get('states_Vx_GS')):.3f}")
    row.append(f"{_safe_float(states_data.get('states_Vy_GS')):.3f}")
    row.append(f"{_safe_float(states_data.get('states_Vz_GS')):.3f}")
    row.append(f"{_safe_float(states_data.get('states_p')):.4f}")
    row.append(f"{_safe_float(states_data.get('states_q')):.4f}")
    row.append(f"{_safe_float(states_data.get('states_r')):.4f}")
    row.append(f"{_safe_float(states_data.get('states_phi')):.4f}")
    row.append(f"{_safe_float(states_data.get('states_theta')):.4f}")
    row.append(f"{_safe_float(states_data.get('states_psi')):.4f}")
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_datactrl_row(timestamp: str, datactrl_data: Dict[str, Any]) -> str:
    """格式化DATACTRL数据行（53列）"""
    row = [timestamp]
    
    # PWMS + STATES为空 (20列)
    row.extend([""] * (COL_TIMESTAMP + COL_PWMS + COL_STATES - 1))
    
    # DATACTRL数据 (53列)
    # ailOutLoop (8)
    ail_out = datactrl_data.get('ailOutLoop', {})
    row.append(f"{_safe_float(ail_out.get('dY_delta')):.4f}")
    row.append(f"{_safe_float(ail_out.get('Vy_dY2Vy')):.4f}")
    row.append(f"{_safe_float(ail_out.get('Vy_var')):.4f}")
    row.append(f"{_safe_float(ail_out.get('Vy_delta')):.4f}")
    row.append(f"{_safe_float(ail_out.get('Vy_P')):.4f}")
    row.append(f"{_safe_float(ail_out.get('Vy_Int')):.4f}")
    row.append(f"{_safe_float(ail_out.get('Vy_D')):.4f}")
    row.append(f"{_safe_float(ail_out.get('ail_ffc')):.4f}")
    
    # ailInLoop (8)
    ail_in = datactrl_data.get('ailInLoop', {})
    row.append(f"{_safe_float(ail_in.get('ail_trim')):.4f}")
    row.append(f"{_safe_float(ail_in.get('phi_trim')):.4f}")
    row.append(f"{_safe_float(ail_in.get('phi_var')):.4f}")
    row.append(f"{_safe_float(ail_in.get('delta_phi')):.4f}")
    row.append(f"{_safe_float(ail_in.get('phi_P')):.4f}")
    row.append(f"{_safe_float(ail_in.get('phi_D')):.4f}")
    row.append(f"{_safe_float(ail_in.get('ail_fbc')):.4f}")
    row.append(f"{_safe_float(ail_in.get('ail_law_out')):.4f}")
    
    # eleOutLoop (8)
    ele_out = datactrl_data.get('eleOutLoop', {})
    row.append(f"{_safe_float(ele_out.get('dX_delta')):.4f}")
    row.append(f"{_safe_float(ele_out.get('Vx_dX2Vx')):.4f}")
    row.append(f"{_safe_float(ele_out.get('Vx_var')):.4f}")
    row.append(f"{_safe_float(ele_out.get('Vx_delta')):.4f}")
    row.append(f"{_safe_float(ele_out.get('Vx_P')):.4f}")
    row.append(f"{_safe_float(ele_out.get('Vx_Int')):.4f}")
    row.append(f"{_safe_float(ele_out.get('Vx_D')):.4f}")
    row.append(f"{_safe_float(ele_out.get('ele_ffc')):.4f}")
    
    # EleInLoop (8)
    ele_in = datactrl_data.get('EleInLoop', {})
    row.append(f"{_safe_float(ele_in.get('theta_trim')):.4f}")
    row.append(f"{_safe_float(ele_in.get('ele_trim')):.4f}")
    row.append(f"{_safe_float(ele_in.get('theta_var')):.4f}")
    row.append(f"{_safe_float(ele_in.get('delta_theta')):.4f}")
    row.append(f"{_safe_float(ele_in.get('theta_P')):.4f}")
    row.append(f"{_safe_float(ele_in.get('theta_D')):.4f}")
    row.append(f"{_safe_float(ele_in.get('ele_fbc')):.4f}")
    row.append(f"{_safe_float(ele_in.get('ele_law_out')):.4f}")
    
    # RudOutLoop (3)
    rud_out = datactrl_data.get('RudOutLoop', {})
    row.append(f"{_safe_float(rud_out.get('psi_dy')):.4f}")
    row.append(f"{_safe_float(rud_out.get('psi_delta')):.4f}")
    row.append(f"{_safe_float(rud_out.get('R_dPsi2R')):.4f}")
    
    # rudInLoop (7)
    rud_in = datactrl_data.get('rudInLoop', {})
    row.append(f"{_safe_float(rud_in.get('rud_trim')):.4f}")
    row.append(f"{_safe_float(rud_in.get('R_var')):.4f}")
    row.append(f"{_safe_float(rud_in.get('dR_delta')):.4f}")
    row.append(f"{_safe_float(rud_in.get('R_P')):.4f}")
    row.append(f"{_safe_float(rud_in.get('R_Int')):.4f}")
    row.append(f"{_safe_float(rud_in.get('rud_fbc')):.4f}")
    row.append(f"{_safe_float(rud_in.get('rud_law_out')):.4f}")
    
    # colOutLoop (8)
    col_out = datactrl_data.get('colOutLoop', {})
    row.append(f"{_safe_float(col_out.get('H_delta')):.4f}")
    row.append(f"{_safe_float(col_out.get('Hdot_dH2Vz')):.4f}")
    row.append(f"{_safe_float(col_out.get('Hdot_var')):.4f}")
    row.append(f"{_safe_float(col_out.get('Hdot_delta')):.4f}")
    row.append(f"{_safe_float(col_out.get('Hdot_P')):.4f}")
    row.append(f"{_safe_float(col_out.get('Hdot_Int')):.4f}")
    row.append(f"{_safe_float(col_out.get('Hdot_D')):.4f}")
    row.append(f"{_safe_float(col_out.get('col_fbc')):.4f}")
    
    # colInLoop (3)
    col_in = datactrl_data.get('colInLoop', {})
    row.append(f"{_safe_float(col_in.get('col_Vx')):.4f}")
    row.append(f"{_safe_float(col_in.get('col_law')):.4f}")
    row.append(f"{_safe_float(col_in.get('col_law_out')):.4f}")
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_gncbus_row(timestamp: str, gncbus_data: Dict[str, Any]) -> str:
    """格式化GNCBUS数据行（75列）"""
    row = [timestamp]
    
    # 前面为空 (73列)
    row.extend([""] * (COL_TIMESTAMP + COL_PWMS + COL_STATES + COL_DATACTRL - 1))
    
    # GNCBUS数据 (75列)
    # TokenMode (17)
    token_mode = gncbus_data.get('TokenMode', {})
    row.append(_safe_str(token_mode.get('OnSky', 0)))
    row.append(_safe_str(token_mode.get('Ctrl_Mode', 0)))
    row.append(_safe_str(token_mode.get('Pre_CMD', 0)))
    row.append(_safe_str(token_mode.get('rud_state', 0)))
    row.append(_safe_str(token_mode.get('ail_state', 0)))
    row.append(_safe_str(token_mode.get('ele_state', 0)))
    row.append(_safe_str(token_mode.get('col_state', 0)))
    row.append(_safe_str(token_mode.get('nav_guid', 0)))
    row.append(_safe_str(token_mode.get('cmd_guid', 0)))
    row.append(_safe_str(token_mode.get('mode_guid', 0)))
    row.append(_safe_str(token_mode.get('step_guid', 0)))
    row.append(_safe_str(token_mode.get('mode_nav', 0)))
    row.append(_safe_str(token_mode.get('token_nav', 0)))
    row.append(_safe_str(token_mode.get('step_nav', 0)))
    row.append(_safe_str(token_mode.get('mode_vert', 0)))
    row.append(_safe_str(token_mode.get('token_vert', 0)))
    row.append(_safe_str(token_mode.get('step_vert', 0)))
    row.append(_safe_str(token_mode.get('mode_horiz', 0)))
    row.append(_safe_str(token_mode.get('token_horiz', 0)))
    
    # FtbOpt (10)
    ftb_opt = gncbus_data.get('FtbOpt', {})
    row.append(f"{_safe_float(ftb_opt.get('ele_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('ail_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('rud_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('col_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('R_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('Vx_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('Vy_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('coldt_opt')):.4f}")
    row.append(f"{_safe_float(ftb_opt.get('col0_opt')):.4f}")
    row.append(_safe_str(ftb_opt.get('Ftb_Switch', 0)))
    
    # SrcValue (2)
    src_value = gncbus_data.get('SrcValue', {})
    row.append(_safe_str(src_value.get('ac_SrcCmdV', 0)))
    row.append(_safe_str(src_value.get('SrcV_fus', 0)))
    
    # MixValue (10)
    mix_value = gncbus_data.get('MixValue', {})
    row.append(f"{_safe_float(mix_value.get('col_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('phi_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('Vx_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('dX_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('theta_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('Vy_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('dY_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('psi_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('Hdot_mix')):.4f}")
    row.append(f"{_safe_float(mix_value.get('height_mix')):.4f}")
    
    # CmdValue (7)
    cmd_value = gncbus_data.get('CmdValue', {})
    row.append(f"{_safe_float(cmd_value.get('phi_cmd')):.4f}")
    row.append(f"{_safe_float(cmd_value.get('Hdot_cmd')):.4f}")
    row.append(f"{_safe_float(cmd_value.get('R_cmd')):.4f}")
    row.append(f"{_safe_float(cmd_value.get('psi_cmd')):.4f}")
    row.append(f"{_safe_float(cmd_value.get('Vx_cmd')):.4f}")
    row.append(f"{_safe_float(cmd_value.get('Vy_cmd')):.4f}")
    row.append(f"{_safe_float(cmd_value.get('height_cmd')):.4f}")
    
    # VarValue (4)
    var_value = gncbus_data.get('VarValue', {})
    row.append(f"{_safe_float(var_value.get('psi_var')):.4f}")
    row.append(f"{_safe_float(var_value.get('height_var')):.4f}")
    row.append(f"{_safe_float(var_value.get('dX_var')):.4f}")
    row.append(f"{_safe_float(var_value.get('dY_var')):.4f}")
    
    # TrimValue (3)
    trim_value = gncbus_data.get('TrimValue', {})
    row.append(f"{_safe_float(trim_value.get('Vx_trim')):.4f}")
    row.append(f"{_safe_float(trim_value.get('col_trim')):.4f}")
    row.append(f"{_safe_float(trim_value.get('col_autotrim')):.4f}")
    
    # ParamsLMT (10)
    params_lmt = gncbus_data.get('ParamsLMT', {})
    row.append(f"{_safe_float(params_lmt.get('Vx_LMT')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Vy_LMT')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('R_LMT')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Hdot_ILmt')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Hdot_UpLMT')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Hdot_DownLMT')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('R_FLYTURN')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('R_unit')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Hdot_unit')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Vx_unit')):.4f}")
    row.append(f"{_safe_float(params_lmt.get('Vy_unit')):.4f}")
    
    # AcValue (4)
    ac_value = gncbus_data.get('AcValue', {})
    row.append(f"{_safe_float(ac_value.get('ac_dY')):.4f}")
    row.append(f"{_safe_float(ac_value.get('ac_dX')):.4f}")
    row.append(f"{_safe_float(ac_value.get('ac_dPsi')):.4f}")
    row.append(f"{_safe_float(ac_value.get('ac_dL')):.4f}")
    
    # HoverValue (3)
    hover_value = gncbus_data.get('HoverValue', {})
    row.append(f"{_safe_float(hover_value.get('lon_hov')):.8f}")
    row.append(f"{_safe_float(hover_value.get('lat_hov')):.8f}")
    row.append(_safe_str(hover_value.get('IsHovStatus_hov', 0)))
    
    # HomeValue (2)
    home_value = gncbus_data.get('HomeValue', {})
    row.append(f"{_safe_float(home_value.get('lon_home')):.8f}")
    row.append(f"{_safe_float(home_value.get('lat_home')):.8f}")
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_voiflag_row(timestamp: str, voiflag_data: Dict[str, Any]) -> str:
    """格式化AVOIFLAG数据行"""
    row = [timestamp]
    
    # 前面为空 (147列)
    row.extend([""] * OFFSET_AVOIFLAG)
    
    # AVOIFLAG数据 (3列)
    row.append(_safe_str(voiflag_data.get('AvoiFlag_LaserRadar_Enabled', 0)))
    row.append(_safe_str(voiflag_data.get('AvoiFlag_AvoidanceFlag', 0)))
    row.append(_safe_str(voiflag_data.get('AvoiFlag_GuideFlag', 0)))
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_futaba_row(timestamp: str, futaba_data: Dict[str, Any]) -> str:
    """格式化FUTABA数据行"""
    row = [timestamp]
    
    # 前面为空 (150列)
    row.extend([""] * OFFSET_FUTABA)
    
    # FUTABA数据 (6列)
    row.append(_safe_str(futaba_data.get('Tele_ftb_Roll', 0)))
    row.append(_safe_str(futaba_data.get('Tele_ftb_Pitch', 0)))
    row.append(_safe_str(futaba_data.get('Tele_ftb_Yaw', 0)))
    row.append(_safe_str(futaba_data.get('Tele_ftb_Col', 0)))
    row.append(_safe_str(futaba_data.get('Tele_ftb_Switch', 0)))
    row.append(_safe_str(futaba_data.get('Tele_ftb_com_Ftb_fail', 0)))
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_gcs_row(timestamp: str, gcs_data: Dict[str, Any]) -> str:
    """格式化GCS数据行 (GCSTelemetry_T)"""
    row = [timestamp]
    
    # 前面为空
    row.extend([""] * OFFSET_GCS)
    
    # GCS数据 (11列)
    row.append(str(gcs_data.get('seq_id', 0)))
    row.append(str(gcs_data.get('timestamp', 0)))
    row.append(f"{_safe_float(gcs_data.get('pos_x')):.4f}")
    row.append(f"{_safe_float(gcs_data.get('pos_y')):.4f}")
    row.append(f"{_safe_float(gcs_data.get('pos_z')):.4f}")
    row.append(f"{_safe_float(gcs_data.get('vel')):.4f}")
    row.append(str(gcs_data.get('update_flags', 0)))
    row.append(str(gcs_data.get('status', 0)))
    row.append(str(gcs_data.get('global_path_count', 0)))
    row.append(str(gcs_data.get('local_traj_count', 0)))
    row.append(str(gcs_data.get('obstacle_count', 0)))
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_aim2ab_row(timestamp: str, aim_data: Dict[str, Any]) -> str:
    """格式化ac_aim2AB数据行（22列）"""
    row = [timestamp]
    
    # 前面为空 (160列)
    row.extend([""] * OFFSET_AC_AIM2AB)
    
    # ac_aim2AB数据 (22列)
    row.append(f"{_safe_float(aim_data.get('lon')):.8f}")
    row.append(f"{_safe_float(aim_data.get('lat')):.8f}")
    row.append(f"{_safe_float(aim_data.get('psi')):.4f}")
    row.append(f"{_safe_float(aim_data.get('alt')):.4f}")
    row.append(f"{_safe_float(aim_data.get('len')):.4f}")
    row.append(f"{_safe_float(aim_data.get('rad')):.4f}")
    row.append(f"{_safe_float(aim_data.get('Vx2nextdot')):.4f}")
    row.append(_safe_str(_safe_int(aim_data.get('next_num'))))
    row.append(_safe_str(_safe_int(aim_data.get('next_dot'))))
    row.append(_safe_str(_safe_int(aim_data.get('type_dot'))))
    row.append(_safe_str(_safe_int(aim_data.get('clockwise_WP'))))
    row.append(f"{_safe_float(aim_data.get('R_WP')):.4f}")
    row.append(_safe_str(_safe_int(aim_data.get('type_WP'))))
    row.append(_safe_str(_safe_int(aim_data.get('Num_type_WP'))))
    row.append(f"{_safe_float(aim_data.get('dL_WP')):.4f}")
    row.append(_safe_str(_safe_int(aim_data.get('Vx_type'))))
    row.append(_safe_str(_safe_int(aim_data.get('TTC_Fault_Mode'))))
    row.append(_safe_str(_safe_int(aim_data.get('deltaY_ctrl'))))
    row.append(_safe_str(_safe_int(aim_data.get('turn_type'))))
    row.append(_safe_str(_safe_int(aim_data.get('Inv_type'))))
    row.append(_safe_str(_safe_int(aim_data.get('type_line'))))
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_acab_row(timestamp: str, ac_data: Dict[str, Any]) -> str:
    """格式化acAB数据行（22列）"""
    row = [timestamp]
    
    # 前面为空 (182列)
    row.extend([""] * OFFSET_AC_AB)
    
    # acAB数据 (22列)
    row.append(f"{_safe_float(ac_data.get('lon')):.8f}")
    row.append(f"{_safe_float(ac_data.get('lat')):.8f}")
    row.append(f"{_safe_float(ac_data.get('psi')):.4f}")
    row.append(f"{_safe_float(ac_data.get('alt')):.4f}")
    row.append(f"{_safe_float(ac_data.get('len')):.4f}")
    row.append(f"{_safe_float(ac_data.get('rad')):.4f}")
    row.append(f"{_safe_float(ac_data.get('Vx2nextdot')):.4f}")
    row.append(_safe_str(_safe_int(ac_data.get('next_num'))))
    row.append(_safe_str(_safe_int(ac_data.get('next_dot'))))
    row.append(_safe_str(_safe_int(ac_data.get('type_dot'))))
    row.append(_safe_str(_safe_int(ac_data.get('clockwise_WP'))))
    row.append(f"{_safe_float(ac_data.get('R_WP')):.4f}")
    row.append(_safe_str(_safe_int(ac_data.get('type_WP'))))
    row.append(_safe_str(_safe_int(ac_data.get('Num_type_WP'))))
    row.append(f"{_safe_float(ac_data.get('dL_WP')):.4f}")
    row.append(_safe_str(_safe_int(ac_data.get('Vx_type'))))
    row.append(_safe_str(_safe_int(ac_data.get('TTC_Fault_Mode'))))
    row.append(_safe_str(_safe_int(ac_data.get('deltaY_ctrl'))))
    row.append(_safe_str(_safe_int(ac_data.get('turn_type'))))
    row.append(_safe_str(_safe_int(ac_data.get('Inv_type'))))
    row.append(_safe_str(_safe_int(ac_data.get('type_line'))))
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_param_row(timestamp: str, param_data: Dict[str, Any]) -> str:
    """格式化PARAM数据行"""
    row = [timestamp]
    
    # 前面为空 (204列)
    row.extend([""] * OFFSET_PARAM)
    
    # PARAM数据 (1列)
    row.append(_safe_str(_safe_int(param_data.get('TimeStamp'))))
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_esc_row(timestamp: str, esc_data: Dict[str, Any]) -> str:
    """格式化ESC数据行（18列）"""
    row = [timestamp]
    
    # 前面为空 (205列)
    row.extend([""] * OFFSET_ESC)
    
    # ESC数据 (18列)
    # 误差计数 (6)
    for i in range(1, 7):
        row.append(_safe_str(_safe_int(esc_data.get(f'esc{i}_error_count', 0))))
    # 转速 (6)
    for i in range(1, 7):
        row.append(_safe_str(_safe_int(esc_data.get(f'esc{i}_rpm', 0))))
    # 功率百分比 (6)
    for i in range(1, 7):
        row.append(_safe_str(_safe_int(esc_data.get(f'esc{i}_power_rating_pct', 0))))
    
    # 应该正好225列，不需要填充
    return ",".join(row)