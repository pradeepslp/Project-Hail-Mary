import asyncio
from sqlalchemy import select
from backend.database import connection
from backend.database.models import KnowledgeGraphNodeModel, KnowledgeGraphEdgeModel
from backend.utils.timezone_helper import ist_now

async def main():
    await connection.init_db()
    async with connection.SessionLocal() as db:
        nodes = await db.execute(select(KnowledgeGraphNodeModel))
        nodes_list = nodes.scalars().all()
        print(f"Total nodes in database: {len(nodes_list)}")
        for n in nodes_list[:5]:
            print(f"Node: ID={n.id}, Name='{n.name}', Type='{n.type}'")
            
        edges = await db.execute(select(KnowledgeGraphEdgeModel))
        edges_list = edges.scalars().all()
        print(f"Total edges in database: {len(edges_list)}")
        for e in edges_list[:5]:
            print(f"Edge: ID={e.id}, Source={e.source_node_id}, Target={e.target_node_id}, Type={e.relationship_type}")

if __name__ == "__main__":
    asyncio.run(main())
