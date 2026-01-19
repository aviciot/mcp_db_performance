"""Test script to verify feedback is being saved to database."""
import asyncio
import asyncpg

async def test_db():
    conn = await asyncpg.connect(
        host='omni_db',
        port=5432,
        database='omni',
        user='omni',
        password='postgres'
    )

    print("=" * 60)
    print("FEEDBACK DATABASE TEST")
    print("=" * 60)

    # Check if feedback table exists
    result = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'mcp_performance'
        AND table_name LIKE '%feedback%'
    """)
    print(f"\n✅ Feedback tables: {[r['table_name'] for r in result]}")

    # Count current submissions
    count = await conn.fetchval("""
        SELECT COUNT(*)
        FROM mcp_performance.feedback_submissions
    """)
    print(f"\n📊 Total submissions in DB: {count}")

    if count > 0:
        # Show latest submissions with quality scores
        recent = await conn.fetch("""
            SELECT id, submission_type, title, quality_score,
                   github_issue_number, github_issue_url, created_at
            FROM mcp_performance.feedback_submissions
            ORDER BY created_at DESC
            LIMIT 5
        """)
        print(f"\n📋 Recent {len(recent)} submissions:")
        print("-" * 60)
        for r in recent:
            print(f"  ID: {r['id']}")
            print(f"  Type: {r['submission_type']}")
            print(f"  Title: {r['title'][:60]}")
            print(f"  Quality Score: {r['quality_score']}/10")
            print(f"  GitHub Issue: #{r['github_issue_number']} - {r['github_issue_url']}")
            print(f"  Created: {r['created_at']}")
            print("-" * 60)
    else:
        print("\n⚠️  No submissions found - try submitting feedback first")

    await conn.close()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_db())
