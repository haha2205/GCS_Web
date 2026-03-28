from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    display_name: str
    environment_class: str
    obstacle_density: str
    wind_level: str
    link_quality: str
    sensor_quality: str
    disturbance_tags: Tuple[str, ...]
    description: str


SCENARIO_REGISTRY: Dict[str, ScenarioDefinition] = {
    'S01_OPEN_NOMINAL': ScenarioDefinition('S01_OPEN_NOMINAL', 'Open Nominal', 'open_field', 'low', 'low', 'nominal', 'nominal', ('nominal',), 'Baseline open-field run without injected stress.'),
    'S02_OPEN_WIND_GUST': ScenarioDefinition('S02_OPEN_WIND_GUST', 'Open Wind Gust', 'open_field', 'low', 'high', 'nominal', 'nominal', ('wind_gust', 'attitude_disturbance'), 'Open-field run with external wind disturbance.'),
    'S03_DENSE_OBSTACLE': ScenarioDefinition('S03_DENSE_OBSTACLE', 'Dense Obstacle', 'corridor_obstacle_zone', 'high', 'medium', 'nominal', 'nominal', ('high_obstacle_density', 'planner_stress'), 'Obstacle-dense route that stresses planning and avoidance.'),
    'S04_LINK_DEGRADED': ScenarioDefinition('S04_LINK_DEGRADED', 'Link Degraded', 'semi_urban', 'medium', 'medium', 'degraded', 'nominal', ('downlink_loss', 'command_delay'), 'Communication link is degraded while the flight mission continues.'),
    'S05_SENSOR_DEGRADED': ScenarioDefinition('S05_SENSOR_DEGRADED', 'Sensor Degraded', 'semi_urban', 'medium', 'medium', 'nominal', 'degraded', ('sensor_drop', 'perception_delay'), 'Sensor quality or perception latency is intentionally degraded.'),
    'S05_COMPOSITE_STRESS': ScenarioDefinition('S05_COMPOSITE_STRESS', 'Composite Stress', 'urban_canyon', 'high', 'high', 'degraded', 'degraded', ('planner_stress', 'downlink_loss', 'sensor_drop', 'wind_gust'), 'Composite stress scenario for architecture switching verification.'),
    'S06_COMPOSITE_STRESS': ScenarioDefinition('S06_COMPOSITE_STRESS', 'Composite Stress', 'urban_canyon', 'high', 'high', 'degraded', 'degraded', ('planner_stress', 'downlink_loss', 'sensor_drop', 'wind_gust'), 'Composite stress scenario for architecture switching verification.'),
}


SCENARIO_ALIASES = {
    'S06_COMPOSITE_STRESS': 'S05_COMPOSITE_STRESS',
}


@dataclass
class RuntimeScenarioContext:
    scenario_id: str
    display_name: str
    source: str
    confidence: float
    environment_class: str
    obstacle_density: str
    wind_level: str
    link_quality: str
    sensor_quality: str
    disturbance_tags: Tuple[str, ...] = field(default_factory=tuple)
    heuristic_tags: Tuple[str, ...] = field(default_factory=tuple)


def get_scenario_definition(scenario_id: str) -> ScenarioDefinition:
    scenario_id = SCENARIO_ALIASES.get(scenario_id, scenario_id)
    if scenario_id not in SCENARIO_REGISTRY:
        return ScenarioDefinition(scenario_id, scenario_id, 'custom', 'unknown', 'unknown', 'unknown', 'unknown', tuple(), 'Custom scenario defined outside the built-in registry.')
    return SCENARIO_REGISTRY[scenario_id]


def _parse_disturbance_tags(value: Any) -> Tuple[str, ...]:
    raw = str(value or '').replace(';', '+').replace(',', '+')
    parts = tuple(part.strip() for part in raw.split('+') if part.strip())
    return parts


def build_heuristic_tags(metrics: Mapping[str, Any]) -> Tuple[str, ...]:
    tags = []
    obstacle_count = int(metrics.get('obstacle_count', 0) or 0)
    planning_time_ms = float(metrics.get('planning_time_ms', 0.0) or 0.0)
    downlink_loss = float(metrics.get('downlink_loss', metrics.get('downlink_loss_rate', 0.0)) or 0.0)
    perception_latency_ms = float(metrics.get('perception_latency_ms', 0.0) or 0.0)
    control_jitter_ms = float(metrics.get('control_jitter_ms', 0.0) or 0.0)

    if obstacle_count >= 8:
        tags.append('high_obstacle_density')
    if planning_time_ms >= 80.0:
        tags.append('planner_stress')
    if downlink_loss >= 0.10:
        tags.append('downlink_loss')
    if perception_latency_ms >= 120.0:
        tags.append('sensor_drop')
    if control_jitter_ms >= 20.0:
        tags.append('attitude_disturbance')
    return tuple(tags)


class ScenarioResolver:
    """Scenario is primarily a case-level preset, with heuristic evidence used only as supplement."""

    def __init__(self, default_scenario_id: str = 'S01_OPEN_NOMINAL'):
        self.default_scenario_id = default_scenario_id

    def resolve(
        self,
        *,
        case_row: Optional[Mapping[str, Any]] = None,
        session_meta: Optional[Mapping[str, Any]] = None,
        latest_metrics: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeScenarioContext:
        scenario_id = self.default_scenario_id
        source = 'default'
        confidence = 0.50

        for candidate_source, payload in (('case_plan', case_row), ('session_meta', session_meta)):
            if payload and payload.get('scenario_id'):
                scenario_id = str(payload['scenario_id'])
                source = candidate_source
                confidence = 1.0
                break

        definition = get_scenario_definition(scenario_id)
        heuristic_tags = build_heuristic_tags(latest_metrics or {})
        case_row = case_row or {}
        display_name = str(case_row.get('scenario_name') or definition.display_name)
        environment_class = str(case_row.get('environment_class') or definition.environment_class)
        obstacle_density = str(case_row.get('obstacle_density') or definition.obstacle_density)
        wind_level = str(case_row.get('wind_level') or definition.wind_level)
        link_quality = str(case_row.get('link_quality') or definition.link_quality)
        sensor_quality = str(case_row.get('sensor_quality') or definition.sensor_quality)
        disturbance_tags = _parse_disturbance_tags(case_row.get('disturbance_profile')) or definition.disturbance_tags
        return RuntimeScenarioContext(
            scenario_id=definition.scenario_id,
            display_name=display_name,
            source=source,
            confidence=confidence,
            environment_class=environment_class,
            obstacle_density=obstacle_density,
            wind_level=wind_level,
            link_quality=link_quality,
            sensor_quality=sensor_quality,
            disturbance_tags=disturbance_tags,
            heuristic_tags=heuristic_tags,
        )


def build_session_meta_patch(case_row: Mapping[str, Any]) -> Dict[str, Any]:
    definition = get_scenario_definition(str(case_row.get('scenario_id', 'S01_OPEN_NOMINAL')))
    disturbance_tags = _parse_disturbance_tags(case_row.get('disturbance_profile')) or definition.disturbance_tags
    return {
        'scenario_id': definition.scenario_id,
        'scenario_name': case_row.get('scenario_name', definition.display_name),
        'environment_class': case_row.get('environment_class', definition.environment_class),
        'obstacle_density': case_row.get('obstacle_density', definition.obstacle_density),
        'wind_level': case_row.get('wind_level', definition.wind_level),
        'link_quality': case_row.get('link_quality', definition.link_quality),
        'sensor_quality': case_row.get('sensor_quality', definition.sensor_quality),
        'disturbance_profile': case_row.get('disturbance_profile', '+'.join(disturbance_tags)),
        'disturbance_tags': list(disturbance_tags),
    }