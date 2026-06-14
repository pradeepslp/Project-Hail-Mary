import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import KnowledgeGraphNodeModel, KnowledgeGraphEdgeModel
from backend.utils.timezone_helper import ist_now

async def seed_knowledge_graph(db: AsyncSession):
    """Pre-seeds the initial knowledge graph nodes and edges if not present"""
    # Check if already seeded
    try:
        node_check = await db.execute(select(KnowledgeGraphNodeModel).limit(1))
        if node_check.scalars().first() is not None:
            return  # Already seeded
    except Exception as e:
        print(f"[KnowledgeGraph] Error checking seeding: {e}")
        return

    print("[KnowledgeGraph] Seeding mission knowledge graph nodes...")
    
    # 1. Nodes definition
    nodes_data = [
        # Events
        {"name": "Solar Storm", "type": "Event", "properties": '{"severity": "CRITICAL", "description": "Solar coronal mass ejection (CME)"}'},
        {"name": "Fuel Leak", "type": "Event", "properties": '{"severity": "HIGH", "description": "Propellant pressure line leak"}'},
        {"name": "Thruster Failure", "type": "Event", "properties": '{"severity": "HIGH", "description": "RCS thruster feedback valve failure"}'},
        {"name": "Communication Loss", "type": "Event", "properties": '{"severity": "HIGH", "description": "HG Antenna carrier tracking loss"}'},
        {"name": "Navigation Drift", "type": "Event", "properties": '{"severity": "LOW", "description": "IMU drift introduces coordinate discrepancies"}'},
        {"name": "Micrometeorite Impact", "type": "Event", "properties": '{"severity": "CRITICAL", "description": "High-velocity micro-impact"}'},
        {"name": "Power Fluctuation", "type": "Event", "properties": '{"severity": "MEDIUM", "description": "Solar array transient discharge"}'},
        {"name": "Sensor Malfunction", "type": "Event", "properties": '{"severity": "LOW", "description": "Optical tracking occlusion"}'},

        # Subsystems
        {"name": "Propulsion", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Propulsion"}'},
        {"name": "Power", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Power"}'},
        {"name": "Navigation", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Navigation"}'},
        {"name": "Communication", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Communication"}'},
        {"name": "Life Support", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Life Support"}'},
        {"name": "Thermal Control", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Thermal Control"}'},
        {"name": "Science Systems", "type": "Subsystem", "properties": '{"health_ref": "subsystems.Science Systems"}'},

        # Actions
        {"name": "Divert Power to Deflectors", "type": "Action", "properties": '{"action_key": "solar_storm_divert_power"}'},
        {"name": "Retract Secondary Panels", "type": "Action", "properties": '{"action_key": "solar_storm_retract_panels"}'},
        {"name": "Activate Backup Tank", "type": "Action", "properties": '{"action_key": "fuel_leak_activate_backup"}'},
        {"name": "Reduce Cruise Speed", "type": "Action", "properties": '{"action_key": "fuel_leak_reduce_speed"}'},
        {"name": "Emergency Shutdown", "type": "Action", "properties": '{"action_key": "fuel_leak_emergency_shutdown"}'},
        {"name": "Re-vector gimbal bells", "type": "Action", "properties": '{"action_key": "thruster_fail_revector"}'},
        {"name": "Enable Backup Controller", "type": "Action", "properties": '{"action_key": "thruster_fail_backup_controller"}'},
        {"name": "Initiate Automated Sweeps", "type": "Action", "properties": '{"action_key": "comm_loss_automated_sweep"}'},
        {"name": "STAR-Field Overlay", "type": "Action", "properties": '{"action_key": "nav_drift_star_field"}'},
        {"name": "Seal Bulkheads", "type": "Action", "properties": '{"action_key": "meteor_seal_pressure"}'},
        {"name": "Run Damage Diagnostics", "type": "Action", "properties": '{"action_key": "meteor_run_diagnostic"}'},

        # Objectives & Outcomes
        {"name": "Reach Tau Ceti Orbit", "type": "Objective", "properties": '{"completion_rate": "100%"}'},
        {"name": "Maximize Propellant Reserves", "type": "Outcome", "properties": '{"optimal_reserves": ">15%"}'},
        {"name": "Maintain Subsystem Integrity", "type": "Outcome", "properties": '{"integrity_floor": ">50%"}'}
    ]

    nodes_map = {}
    for node_info in nodes_data:
        node = KnowledgeGraphNodeModel(
            name=node_info["name"],
            type=node_info["type"],
            properties=node_info["properties"]
        )
        db.add(node)
        await db.flush()
        # Save ID locally for edge seeding mapping
        nodes_map[node_info["name"]] = node.id

    print("[KnowledgeGraph] Seeding mission knowledge graph edges...")
    
    # 2. Edges definition
    edges_data = [
        # (source, target, relationship_type, weight)
        ("Solar Storm", "Communication Loss", "Triggers", 0.7),
        ("Solar Storm", "Power", "Damages", 0.5),
        ("Fuel Leak", "Thruster Failure", "Triggers", 0.6),
        ("Fuel Leak", "Propulsion", "Damages", 0.4),
        ("Thruster Failure", "Navigation Drift", "Causes", 0.4),
        ("Navigation Drift", "Navigation", "Damages", 0.5),
        ("Power Fluctuation", "Sensor Malfunction", "Triggers", 0.5),
        ("Power Fluctuation", "Power", "Damages", 0.3),
        
        # Actions mitigations
        ("Divert Power to Deflectors", "Solar Storm", "Mitigates", 0.9),
        ("Retract Secondary Panels", "Solar Storm", "Mitigates", 0.75),
        ("Activate Backup Tank", "Fuel Leak", "Mitigates", 0.8),
        ("Reduce Cruise Speed", "Fuel Leak", "Mitigates", 0.4),
        ("Emergency Shutdown", "Fuel Leak", "Mitigates", 0.95),
        ("Re-vector gimbal bells", "Thruster Failure", "Mitigates", 0.7),
        ("Enable Backup Controller", "Thruster Failure", "Mitigates", 0.85),
        ("Initiate Automated Sweeps", "Communication Loss", "Mitigates", 0.8),
        ("STAR-Field Overlay", "Navigation Drift", "Mitigates", 0.85),
        ("Seal Bulkheads", "Micrometeorite Impact", "Mitigates", 0.8),
        ("Run Damage Diagnostics", "Micrometeorite Impact", "Mitigates", 0.6),
        
        # Objectives links
        ("Reach Tau Ceti Orbit", "Maximize Propellant Reserves", "Improves", 0.5),
        ("Reach Tau Ceti Orbit", "Maintain Subsystem Integrity", "Improves", 0.5)
    ]

    for source_name, target_name, rel, weight in edges_data:
        src_id = nodes_map.get(source_name)
        tgt_id = nodes_map.get(target_name)
        if src_id and tgt_id:
            edge = KnowledgeGraphEdgeModel(
                source_node_id=src_id,
                target_node_id=tgt_id,
                relationship_type=rel,
                weight=weight
            )
            db.add(edge)

    await db.commit()
    print("[KnowledgeGraph] Graph seeding completed successfully.")

async def get_knowledge_graph(db: AsyncSession):
    """Queries all nodes and edges in the Knowledge Graph"""
    nodes_res = await db.execute(select(KnowledgeGraphNodeModel))
    nodes = nodes_res.scalars().all()
    
    edges_res = await db.execute(select(KnowledgeGraphEdgeModel))
    edges = edges_res.scalars().all()
    
    nodes_list = []
    nodes_id_map = {}
    for node in nodes:
        props = {}
        try:
            props = json.loads(node.properties)
        except Exception:
            pass
        nodes_list.append({
            "id": node.id,
            "name": node.name,
            "type": node.type,
            "properties": props
        })
        nodes_id_map[node.id] = node.name

    edges_list = []
    for edge in edges:
        edges_list.append({
            "id": edge.id,
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            "source_name": nodes_id_map.get(edge.source_node_id, "Unknown"),
            "target_name": nodes_id_map.get(edge.target_node_id, "Unknown"),
            "type": edge.relationship_type,
            "weight": edge.weight
        })

    return {
        "nodes": nodes_list,
        "edges": edges_list
    }
