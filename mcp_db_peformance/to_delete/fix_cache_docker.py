#!/usr/bin/env python3
"""
Docker-based cache fix script
Runs inside the MCP Docker container to fix PostgreSQL cache
"""

import asyncio
import sys
import os
import logging
import traceback

# We're already in the container, so paths are correct
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("docker_cache_fix")

async def main():
    """Run the complete cache fix inside Docker container."""
    
    print("🐳 Docker Container Cache Fix")
    print("🔧 Fixing PostgreSQL cache for explain_business_logic")
    print("=" * 80)
    
    try:
        # Import our fix function
        sys.path.append('/app')
        
        # Run the complete fix
        from fix_cache_complete import main as fix_main
        success = await fix_main()
        
        if success:
            print("\n🎉 Cache fix completed successfully!")
            print("💡 Now test with: python test_cache_after_fix.py")
        else:
            print("\n❌ Cache fix failed - check errors above")
        
        return success
        
    except Exception as e:
        print(f"💥 Cache fix crashed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Cache fix interrupted")
        sys.exit(1)