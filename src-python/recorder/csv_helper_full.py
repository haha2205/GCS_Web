"""
CSV数据记录辅助函数（完整版）
基于interface.h中完整的ExtY_FCS_T结构体定义
实现"宽表"格式的CSV记录（不带category列）
"""

from typing import Dict, Any
from datetime import datetime


# ==================== 列数常量 ====================

# 总列数（重新核对）
# 1 + 8 + 12 + 53 + 73 + 3 + 6 + 4 + 21 + 21 + 30 + 36 = 268
TOTAL_COLUMNS = 268

# 各数据段的列数（根据interface.h严格计数）
COL_TIMESTAMP = 1
COL_PWMS = 8
COL_STATES = 12
COL_DATACTRL = 53
COL_GNCBUS = 73     
COL_AVOIFLAG = 3
COL_FUTABA = 6
COL_GCS = 4        
COL_AC_AIM2AB = 21 
COL_AC_AB = 21      
COL_PARAM = 30
COL_ESC = 36

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


def _get_value(data: Dict[str, Any], *candidates, default=0):
    """按候选路径获取字段，兼容扁平和嵌套 payload。"""
    for candidate in candidates:
        if isinstance(candidate, str):
            if candidate in data:
                return data.get(candidate, default)
            continue

        current = data
        matched = True
        for key in candidate:
            if not isinstance(current, dict) or key not in current:
                matched = False
                break
            current = current[key]
        if matched:
            return current
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
    
    # 5. GNCBUS数据 (73字段)
    # TokenMode (17) - Fixed: removed mode_horiz/token_horiz
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
        "GNCBus_TokenMode_step_vert"
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
    
    # 8. DATAGCS数据 (4字段) - Fixed: removed extra planning fields
    header_fields.extend([
        "Tele_GCS_CmdIdx",
        "Tele_GCS_Mission",
        "Tele_GCS_Val",
        "Tele_GCS_com_GCS_fail"
    ])
    
    # 9. ac_aim2AB数据 (21字段)
    header_fields.extend([
        "ac_aim2AB_lon", "ac_aim2AB_lat", "ac_aim2AB_psi", "ac_aim2AB_alt",
        "ac_aim2AB_len", "ac_aim2AB_rad", "ac_aim2AB_Vx2nextdot",
        "ac_aim2AB_next_num", "ac_aim2AB_next_dot", "ac_aim2AB_type_dot",
        "ac_aim2AB_clockwise_WP", "ac_aim2AB_R_WP", "ac_aim2AB_type_WP",
        "ac_aim2AB_Num_type_WP", "ac_aim2AB_dL_WP", "ac_aim2AB_Vx_type",
        "ac_aim2AB_TTC_Fault_Mode", "ac_aim2AB_deltaY_ctrl",
        "ac_aim2AB_turn_type", "ac_aim2AB_Inv_type", "ac_aim2AB_type_line"
    ])
    
    # 10. acAB数据 (21字段)
    header_fields.extend([
        "acAB_lon", "acAB_lat", "acAB_psi", "acAB_alt",
        "acAB_len", "acAB_rad", "acAB_Vx2nextdot",
        "acAB_next_num", "acAB_next_dot", "acAB_type_dot",
        "acAB_clockwise_WP", "acAB_R_WP", "acAB_type_WP",
        "acAB_Num_type_WP", "acAB_dL_WP", "acAB_Vx_type",
        "acAB_TTC_Fault_Mode", "acAB_deltaY_ctrl",
        "acAB_turn_type", "acAB_Inv_type", "acAB_type_line"
    ])
    
    # 11. PARAMS数据 (30字段)
    header_fields.extend([
        "ParamAil_F_KaPHI", "ParamAil_F_KaP", "ParamAil_F_KaY", "ParamAil_F_IaY",
        "ParamAil_F_KaVy", "ParamAil_F_IaVy", "ParamAil_F_KaAy", "ParamAil_YaccLMT",
        "ParamEle_F_KeTHETA", "ParamEle_F_KeQ", "ParamEle_F_KeX", "ParamEle_F_IeX",
        "ParamEle_F_KeVx", "ParamEle_F_IeVx", "ParamEle_F_KeAx", "ParamEle_XaccLMT",
        "ParamRud_F_KrR", "ParamRud_F_IrR", "ParamRud_F_KrAy", "ParamRud_F_KrPSI",
        "ParamH_F_KcH", "ParamH_F_IcH", "ParamH_F_KcHdot", "ParamH_F_IcHdot", "ParamH_F_KcAz",
        "ParamRPM_F_KgRPM", "ParamRPM_F_IgRPM",
        "ParamScale_F_scale_factor", "ParamGuide_Hground", "ParamGuide_AutoTakeoffHcmd"
    ])
    
    # 12. ESC数据 (36字段)
    for i in range(1, 7):
        header_fields.append(f"esc{i}_error_count")
    for i in range(1, 7):
        header_fields.append(f"esc{i}_voltage")
    for i in range(1, 7):
        header_fields.append(f"esc{i}_current")
    for i in range(1, 7):
        header_fields.append(f"esc{i}_temperature")
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
        CSV格式字符串（总221列）
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
        elif data_type == 'fcs_datagcs':  # Fixed: Only fcs_datagcs uses this, NOT planning_telemetry
            return _format_gcs_row(timestamp, telemetry_data)
        elif data_type == 'fcs_line_aim2ab':
            return _format_aim2ab_row(timestamp, telemetry_data)
        elif data_type == 'fcs_line_ab':
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
    row.extend([""] * (OFFSET_DATACTRL - 1))
    
    def get_val(flat_key, *path):
        candidates = [flat_key]
        if path:
            candidates.append(path)
        return _get_value(datactrl_data, *candidates, default=0)

    # ailOutLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_dY_delta', 'ailOutLoop', 'dY_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_Vy_dY2Vy', 'ailOutLoop', 'Vy_dY2Vy')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_Vy_var', 'ailOutLoop', 'Vy_var')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_Vy_delta', 'ailOutLoop', 'Vy_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_Vy_P', 'ailOutLoop', 'Vy_P')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_Vy_Int', 'ailOutLoop', 'Vy_Int')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_Vy_D', 'ailOutLoop', 'Vy_D')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailOutLoop_ail_ffc', 'ailOutLoop', 'ail_ffc')):.4f}")
    
    # ailInLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_ail_trim', 'ailInLoop', 'ail_trim')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_phi_trim', 'ailInLoop', 'phi_trim')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_phi_var', 'ailInLoop', 'phi_var')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_delta_phi', 'ailInLoop', 'delta_phi')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_phi_P', 'ailInLoop', 'phi_P')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_phi_D', 'ailInLoop', 'phi_D')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_ail_fbc', 'ailInLoop', 'ail_fbc')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_ailInLoop_ail_law_out', 'ailInLoop', 'ail_law_out')):.4f}")

    # eleOutLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_dX_delta', 'eleOutLoop', 'dX_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_Vx_dX2Vx', 'eleOutLoop', 'Vx_dX2Vx')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_Vx_var', 'eleOutLoop', 'Vx_var')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_Vx_delta', 'eleOutLoop', 'Vx_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_Vx_P', 'eleOutLoop', 'Vx_P')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_Vx_Int', 'eleOutLoop', 'Vx_Int')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_Vx_D', 'eleOutLoop', 'Vx_D')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_eleOutLoop_ele_ffc', 'eleOutLoop', 'ele_ffc')):.4f}")

    # EleInLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_theta_trim', 'EleInLoop', 'theta_trim')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_ele_trim', 'EleInLoop', 'ele_trim')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_theta_var', 'EleInLoop', 'theta_var')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_delta_theta', 'EleInLoop', 'delta_theta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_theta_P', 'EleInLoop', 'theta_P')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_theta_D', 'EleInLoop', 'theta_D')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_ele_fbc', 'EleInLoop', 'ele_fbc')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_EleInLoop_ele_law_out', 'EleInLoop', 'ele_law_out')):.4f}")

    # RudOutLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_RudOutLoop_psi_dy', 'RudOutLoop', 'psi_dy')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_RudOutLoop_psi_delta', 'RudOutLoop', 'psi_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_RudOutLoop_R_dPsi2R', 'RudOutLoop', 'R_dPsi2R')):.4f}")

    # rudInLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_rud_trim', 'rudInLoop', 'rud_trim')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_R_var', 'rudInLoop', 'R_var')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_dR_delta', 'rudInLoop', 'dR_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_R_P', 'rudInLoop', 'R_P')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_R_Int', 'rudInLoop', 'R_Int')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_rud_fbc', 'rudInLoop', 'rud_fbc')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_rudInLoop_rud_law_out', 'rudInLoop', 'rud_law_out')):.4f}")

    # colOutLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_H_delta', 'colOutLoop', 'H_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_Hdot_dH2Vz', 'colOutLoop', 'Hdot_dH2Vz')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_Hdot_var', 'colOutLoop', 'Hdot_var')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_Hdot_delta', 'colOutLoop', 'Hdot_delta')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_Hdot_P', 'colOutLoop', 'Hdot_P')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_Hdot_Int', 'colOutLoop', 'Hdot_Int')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_Hdot_D', 'colOutLoop', 'Hdot_D')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colOutLoop_col_fbc', 'colOutLoop', 'col_fbc')):.4f}")

    # colInLoop
    row.append(f"{_safe_float(get_val('dataCtrl_n_colInLoop_col_Vx', 'colInLoop', 'col_Vx')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colInLoop_col_law', 'colInLoop', 'col_law')):.4f}")
    row.append(f"{_safe_float(get_val('dataCtrl_n_colInLoop_col_law_out', 'colInLoop', 'col_law_out')):.4f}")
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_gncbus_row(timestamp: str, gncbus_data: Dict[str, Any]) -> str:
    """格式化GNCBUS数据行（73列）"""
    row = [timestamp]
    
    # 前面为空
    row.extend([""] * (OFFSET_GNCBUS - 1))
    
    def flat_or_nested(flat_key, group_key=None, nested_key=None, default=0):
        if flat_key in gncbus_data:
            return gncbus_data.get(flat_key, default)
        if group_key:
            group = gncbus_data.get(group_key, {}) or {}
            if nested_key in group:
                return group.get(nested_key, default)
        return default

    token_mode = gncbus_data.get('TokenMode', {}) or {}
    row.append(str(flat_or_nested('GNCBus_TokenMode_OnSky', 'TokenMode', 'OnSky', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_Ctrl_Mode', 'TokenMode', 'Ctrl_Mode', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_Pre_CMD', 'TokenMode', 'Pre_CMD', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_rud_state', 'TokenMode', 'rud_state', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_ail_state', 'TokenMode', 'ail_state', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_ele_state', 'TokenMode', 'ele_state', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_col_state', 'TokenMode', 'col_state', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_nav_guid', 'TokenMode', 'nav_guid', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_cmd_guid', 'TokenMode', 'cmd_guid', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_mode_guid', 'TokenMode', 'mode_guid', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_step_guid', 'TokenMode', 'step_guid', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_mode_nav', 'TokenMode', 'mode_nav', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_token_nav', 'TokenMode', 'token_nav', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_step_nav', 'TokenMode', 'step_nav', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_mode_vert', 'TokenMode', 'mode_vert', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_token_vert', 'TokenMode', 'token_vert', 0)))
    row.append(str(flat_or_nested('GNCBus_TokenMode_step_vert', 'TokenMode', 'step_vert', 0)))

    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_ele_opt', 'FtbOpt', 'ele_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_ail_opt', 'FtbOpt', 'ail_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_rud_opt', 'FtbOpt', 'rud_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_col_opt', 'FtbOpt', 'col_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_R_opt', 'FtbOpt', 'R_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_Vx_opt', 'FtbOpt', 'Vx_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_Vy_opt', 'FtbOpt', 'Vy_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_coldt_opt', 'FtbOpt', 'coldt_opt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_FtbOpt_col0_opt', 'FtbOpt', 'col0_opt')):.4f}")
    row.append(str(flat_or_nested('GNCBus_FtbOpt_Ftb_Switch', 'FtbOpt', 'Ftb_Switch', 0)))

    row.append(str(flat_or_nested('GNCBus_SrcValue_ac_SrcCmdV', 'SrcValue', 'ac_SrcCmdV', 0)))
    row.append(str(flat_or_nested('GNCBus_SrcValue_SrcV_fus', 'SrcValue', 'SrcV_fus', 0)))

    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_col_mix', 'MixValue', 'col_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_phi_mix', 'MixValue', 'phi_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_Vx_mix', 'MixValue', 'Vx_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_dX_mix', 'MixValue', 'dX_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_theta_mix', 'MixValue', 'theta_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_Vy_mix', 'MixValue', 'Vy_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_dY_mix', 'MixValue', 'dY_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_psi_mix', 'MixValue', 'psi_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_Hdot_mix', 'MixValue', 'Hdot_mix')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_MixValue_height_mix', 'MixValue', 'height_mix')):.4f}")

    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_phi_cmd', 'CmdValue', 'phi_cmd')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_Hdot_cmd', 'CmdValue', 'Hdot_cmd')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_R_cmd', 'CmdValue', 'R_cmd')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_psi_cmd', 'CmdValue', 'psi_cmd')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_Vx_cmd', 'CmdValue', 'Vx_cmd')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_Vy_cmd', 'CmdValue', 'Vy_cmd')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_CmdValue_height_cmd', 'CmdValue', 'height_cmd')):.4f}")

    row.append(f"{_safe_float(flat_or_nested('GNCBus_VarValue_psi_var', 'VarValue', 'psi_var')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_VarValue_height_var', 'VarValue', 'height_var')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_VarValue_dX_var', 'VarValue', 'dX_var')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_VarValue_dY_var', 'VarValue', 'dY_var')):.4f}")

    row.append(f"{_safe_float(flat_or_nested('GNCBus_TrimValue_Vx_trim', 'TrimValue', 'Vx_trim')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_TrimValue_col_trim', 'TrimValue', 'col_trim')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_TrimValue_col_autotrim', 'TrimValue', 'col_autotrim')):.4f}")

    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Vx_LMT', 'ParamsLMT', 'Vx_LMT')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Vy_LMT', 'ParamsLMT', 'Vy_LMT')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_R_LMT', 'ParamsLMT', 'R_LMT')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Hdot_ILmt', 'ParamsLMT', 'Hdot_ILmt')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Hdot_UpLMT', 'ParamsLMT', 'Hdot_UpLMT')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Hdot_DownLMT', 'ParamsLMT', 'Hdot_DownLMT')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_R_FLYTURN', 'ParamsLMT', 'R_FLYTURN')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_R_unit', 'ParamsLMT', 'R_unit')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Hdot_unit', 'ParamsLMT', 'Hdot_unit')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Vx_unit', 'ParamsLMT', 'Vx_unit')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_ParamsLMT_Vy_unit', 'ParamsLMT', 'Vy_unit')):.4f}")

    row.append(f"{_safe_float(flat_or_nested('GNCBus_AcValue_ac_dY', 'AcValue', 'ac_dY')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_AcValue_ac_dX', 'AcValue', 'ac_dX')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_AcValue_ac_dPsi', 'AcValue', 'ac_dPsi')):.4f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_AcValue_ac_dL', 'AcValue', 'ac_dL')):.4f}")

    row.append(f"{_safe_float(flat_or_nested('GNCBus_HoverValue_lon_hov', 'HoverValue', 'lon_hov')):.8f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_HoverValue_lat_hov', 'HoverValue', 'lat_hov')):.8f}")
    row.append(str(flat_or_nested('GNCBus_HoverValue_IsHovStatus_hov', 'HoverValue', 'IsHovStatus_hov', 0)))

    row.append(f"{_safe_float(flat_or_nested('GNCBus_HomeValue_lon_home', 'HomeValue', 'lon_home')):.8f}")
    row.append(f"{_safe_float(flat_or_nested('GNCBus_HomeValue_lat_home', 'HomeValue', 'lat_home')):.8f}")
    
    # 其他全部为空
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    
    return ",".join(row)


def _format_voiflag_row(timestamp: str, data: Dict[str, Any]) -> str:
    row = [timestamp]
    row.extend([""] * (OFFSET_AVOIFLAG - 1))
    row.append(str(int(bool(data.get('AvoiFlag_LaserRadar_Enabled', data.get('laser_radar_enabled', 0))))))
    row.append(str(int(bool(data.get('AvoiFlag_AvoidanceFlag', data.get('avoidance_flag', 0))))))
    row.append(str(int(bool(data.get('AvoiFlag_GuideFlag', data.get('guide_flag', 0))))))
    row.extend([""] * (TOTAL_COLUMNS - len(row)))
    return ",".join(row)

def _format_futaba_row(timestamp: str, data: Dict[str, Any]) -> str:
    row = [timestamp]
    row.extend([""] * (OFFSET_FUTABA - 1))
    row.append(str(_safe_int(data.get('Tele_ftb_Roll', data.get('roll', 0)))))
    row.append(str(_safe_int(data.get('Tele_ftb_Pitch', data.get('pitch', 0)))))
    row.append(str(_safe_int(data.get('Tele_ftb_Yaw', data.get('yaw', 0)))))
    row.append(str(_safe_int(data.get('Tele_ftb_Col', data.get('col', 0)))))
    row.append(str(_safe_int(data.get('Tele_ftb_Switch', data.get('switch', 0)))))
    row.append(str(_safe_int(data.get('Tele_ftb_com_Ftb_fail', data.get('ftb_fail', 0)))))
    row.extend([""] * (TOTAL_COLUMNS - len(row)))
    return ",".join(row)

def _format_gcs_row(timestamp: str, data: Dict[str, Any]) -> str:
    row = [timestamp]
    row.extend([""] * (OFFSET_GCS - 1))
    row.append(str(_safe_int(data.get('Tele_GCS_CmdIdx', data.get('CmdIdx', 0)))))
    row.append(str(_safe_int(data.get('Tele_GCS_Mission', data.get('Mission', 0)))))
    row.append(f"{_safe_float(data.get('Tele_GCS_Val', data.get('Val', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('Tele_GCS_com_GCS_fail', data.get('fail', 0)))))
    row.extend([""] * (TOTAL_COLUMNS - len(row)))
    return ",".join(row)

def _format_aim2ab_row(timestamp: str, data: Dict[str, Any]) -> str:
    row = [timestamp]
    row.extend([""] * (OFFSET_AC_AIM2AB - 1))
    row.append(f"{_safe_float(data.get('ac_aim2AB_lon', data.get('lon', 0.0))):.8f}")
    row.append(f"{_safe_float(data.get('ac_aim2AB_lat', data.get('lat', 0.0))):.8f}")
    row.append(f"{_safe_float(data.get('ac_aim2AB_psi', data.get('psi', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('ac_aim2AB_alt', data.get('alt', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('ac_aim2AB_len', data.get('len', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('ac_aim2AB_rad', data.get('rad', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('ac_aim2AB_Vx2nextdot', data.get('Vx2nextdot', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('ac_aim2AB_next_num', data.get('next_num', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_next_dot', data.get('next_dot', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_type_dot', data.get('type_dot', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_clockwise_WP', data.get('clockwise_WP', 0)))))
    row.append(f"{_safe_float(data.get('ac_aim2AB_R_WP', data.get('R_WP', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('ac_aim2AB_type_WP', data.get('type_WP', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_Num_type_WP', data.get('Num_type_WP', 0)))))
    row.append(f"{_safe_float(data.get('ac_aim2AB_dL_WP', data.get('dL_WP', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('ac_aim2AB_Vx_type', data.get('Vx_type', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_TTC_Fault_Mode', data.get('TTC_Fault_Mode', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_deltaY_ctrl', data.get('deltaY_ctrl', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_turn_type', data.get('turn_type', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_Inv_type', data.get('Inv_type', 0)))))
    row.append(str(_safe_int(data.get('ac_aim2AB_type_line', data.get('type_line', 0)))))
    row.extend([""] * (TOTAL_COLUMNS - len(row)))
    return ",".join(row)

def _format_acab_row(timestamp: str, data: Dict[str, Any]) -> str:
    row = [timestamp]
    row.extend([""] * (OFFSET_AC_AB - 1))
    row.append(f"{_safe_float(data.get('acAB_lon', data.get('lon', 0.0))):.8f}")
    row.append(f"{_safe_float(data.get('acAB_lat', data.get('lat', 0.0))):.8f}")
    row.append(f"{_safe_float(data.get('acAB_psi', data.get('psi', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('acAB_alt', data.get('alt', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('acAB_len', data.get('len', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('acAB_rad', data.get('rad', 0.0))):.4f}")
    row.append(f"{_safe_float(data.get('acAB_Vx2nextdot', data.get('Vx2nextdot', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('acAB_next_num', data.get('next_num', 0)))))
    row.append(str(_safe_int(data.get('acAB_next_dot', data.get('next_dot', 0)))))
    row.append(str(_safe_int(data.get('acAB_type_dot', data.get('type_dot', 0)))))
    row.append(str(_safe_int(data.get('acAB_clockwise_WP', data.get('clockwise_WP', 0)))))
    row.append(f"{_safe_float(data.get('acAB_R_WP', data.get('R_WP', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('acAB_type_WP', data.get('type_WP', 0)))))
    row.append(str(_safe_int(data.get('acAB_Num_type_WP', data.get('Num_type_WP', 0)))))
    row.append(f"{_safe_float(data.get('acAB_dL_WP', data.get('dL_WP', 0.0))):.4f}")
    row.append(str(_safe_int(data.get('acAB_Vx_type', data.get('Vx_type', 0)))))
    row.append(str(_safe_int(data.get('acAB_TTC_Fault_Mode', data.get('TTC_Fault_Mode', 0)))))
    row.append(str(_safe_int(data.get('acAB_deltaY_ctrl', data.get('deltaY_ctrl', 0)))))
    row.append(str(_safe_int(data.get('acAB_turn_type', data.get('turn_type', 0)))))
    row.append(str(_safe_int(data.get('acAB_Inv_type', data.get('Inv_type', 0)))))
    row.append(str(_safe_int(data.get('acAB_type_line', data.get('type_line', 0)))))
    row.extend([""] * (TOTAL_COLUMNS - len(row)))
    return ",".join(row)

def _format_param_row(timestamp: str, param_data: Dict[str, Any]) -> str:
    """Format PARAM data row (30 columns)."""
    row = [timestamp]
    row.extend([""] * (OFFSET_PARAM - 1))
    
    keys = [
        "ParamAil_F_KaPHI", "ParamAil_F_KaP", "ParamAil_F_KaY", "ParamAil_F_IaY",
        "ParamAil_F_KaVy", "ParamAil_F_IaVy", "ParamAil_F_KaAy", "ParamAil_YaccLMT",
        "ParamEle_F_KeTHETA", "ParamEle_F_KeQ", "ParamEle_F_KeX", "ParamEle_F_IeX",
        "ParamEle_F_KeVx", "ParamEle_F_IeVx", "ParamEle_F_KeAx", "ParamEle_XaccLMT",
        "ParamRud_F_KrR", "ParamRud_F_IrR", "ParamRud_F_KrAy", "ParamRud_F_KrPSI",
        "ParamH_F_KcH", "ParamH_F_IcH", "ParamH_F_KcHdot", "ParamH_F_IcHdot", "ParamH_F_KcAz",
        "ParamRPM_F_KgRPM", "ParamRPM_F_IgRPM",
        "ParamScale_F_scale_factor", "ParamGuide_Hground", "ParamGuide_AutoTakeoffHcmd"
    ]
    
    for key in keys:
        val = param_data.get(key, 0.0)
        row.append(f"{_safe_float(val):.4f}")
        
    fill_count = TOTAL_COLUMNS - len(row)
    row.extend([""] * fill_count)
    return ",".join(row)


def _format_esc_row(timestamp: str, esc_data: Dict[str, Any]) -> str:
    """Format ESC data row (36 columns)."""
    row = [timestamp]
    row.extend([""] * (OFFSET_ESC - 1))

    for i in range(1, 7):
        row.append(str(_safe_int(esc_data.get(f'esc{i}_error_count', 0))))
    for i in range(1, 7):
        row.append(f"{_safe_float(esc_data.get(f'esc{i}_voltage', 0.0)):.4f}")
    for i in range(1, 7):
        row.append(f"{_safe_float(esc_data.get(f'esc{i}_current', 0.0)):.4f}")
    for i in range(1, 7):
        row.append(f"{_safe_float(esc_data.get(f'esc{i}_temperature', 0.0)):.4f}")
    for i in range(1, 7):
        row.append(str(_safe_int(esc_data.get(f'esc{i}_rpm', 0))))
    for i in range(1, 7):
        row.append(str(_safe_int(esc_data.get(f'esc{i}_power_rating_pct', 0))))

    row.extend([""] * (TOTAL_COLUMNS - len(row)))
    return ",".join(row)


def update_cache_and_get_line(data_type: str, data: Dict[str, Any], cache_list: list) -> str:
    """
    更新缓存并返回合并后的CSV行 (Stateful Recording)
    """
    try:
        timestamp = _safe_str(data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]))
        
        # 1. 始终更新时间戳
        if len(cache_list) > 0:
            cache_list[0] = timestamp
        
        # 2. 生成该类型的"稀疏行" (仅包含当前帧的数据)
        row_str = get_data_for_type(data_type, data)
        parts = row_str.split(',')
        
        # 3. 将新数据合并入缓存（"Last Known Value" 策略）
        # 遍历新生成的行，只有当某个字段非空时，才更新缓存
        # 这样可以保留其他包（如 states, pwms）的历史值，实现"宽行"填满
        count = min(len(parts), len(cache_list))
        for i in range(1, count):  # 跳过索引0 (timestamp已处理)
            if parts[i] != "":
                cache_list[i] = parts[i]
                
        return ",".join(cache_list)
    except Exception as e:
        return ",".join(cache_list)

