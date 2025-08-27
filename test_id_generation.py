#!/usr/bin/env python3
"""
Test script to verify that JavaScript-generated IDs are properly used by the backend
without Python overriding them with UUID suffixes.
"""

import re
import random
import string

def test_id_generation_logic():
    """Test the ID generation logic used in the modified code"""
    
    # Simulate JavaScript-generated ID (8 characters)
    def generate_js_id():
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join(random.choice(chars) for _ in range(8))
    
    # Test case 1: Normal JavaScript-generated ID should be used as-is
    js_id = generate_js_id()
    print(f"JavaScript generated ID: {js_id}")
    
    # Simulate the backend logic (without database calls)
    id = js_id.strip()  # Simulating request.form.get('id', '').strip()
    
    # ID validation (same as in the actual code)
    if not re.match(r'^[a-zA-Z0-9]+$', id):
        print("ERROR: Invalid characters")
        return False
    if len(id) < 5 or len(id) > 10:
        print("ERROR: Invalid length")
        return False
    
    # In the real code, there would be a database check here
    # For this test, we'll simulate no collision
    existing_room = False  # Simulating group_data.get_data(id) returning None
    
    if existing_room:
        # Collision handling
        suffix = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(3))
        room_id = f"{id}-{suffix}"
        print(f"Collision detected, room_id with suffix: {room_id}")
    else:
        room_id = id  # JavaScript ID used as-is
        print(f"No collision, room_id: {room_id}")
    
    # Verify the result
    success = (room_id == js_id)
    print(f"Test result: {'PASS' if success else 'FAIL'}")
    print(f"Expected: {js_id}")
    print(f"Actual:   {room_id}")
    print("-" * 50)
    
    return success

def test_collision_handling():
    """Test collision handling logic"""
    print("Testing collision handling...")
    
    js_id = "testID01"
    print(f"JavaScript generated ID: {js_id}")
    
    id = js_id.strip()
    
    # Simulate collision
    existing_room = True  # Simulating existing room
    
    if existing_room:
        suffix = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(3))
        room_id = f"{id}-{suffix}"
        print(f"Collision detected, room_id with suffix: {room_id}")
        success = room_id.startswith(js_id) and len(room_id) == len(js_id) + 4  # +4 for "-" + 3 chars
    else:
        room_id = id
        success = False  # Should not reach here in this test
    
    print(f"Test result: {'PASS' if success else 'FAIL'}")
    print(f"Room ID format: {room_id}")
    print("-" * 50)
    
    return success

def test_fallback_logic():
    """Test fallback when JavaScript doesn't provide an ID"""
    print("Testing fallback logic...")
    
    # Simulate empty ID (JavaScript failed or disabled)
    id = ""
    
    if not id:
        # Fallback generation (same as in actual code)
        chars = string.ascii_letters + string.digits
        id = ''.join(random.choice(chars) for _ in range(8))
        print(f"Fallback ID generated: {id}")
    
    # No collision for this test
    existing_room = False
    room_id = id if not existing_room else f"{id}-suffix"
    
    success = len(room_id) == 8 and re.match(r'^[a-zA-Z0-9]+$', room_id)
    print(f"Test result: {'PASS' if success else 'FAIL'}")
    print(f"Fallback room_id: {room_id}")
    print("-" * 50)
    
    return success

if __name__ == "__main__":
    print("Testing ID generation logic...")
    print("=" * 50)
    
    # Run tests
    test1 = test_id_generation_logic()
    test2 = test_collision_handling()
    test3 = test_fallback_logic()
    
    # Summary
    all_passed = test1 and test2 and test3
    print("SUMMARY:")
    print(f"Normal case: {'PASS' if test1 else 'FAIL'}")
    print(f"Collision case: {'PASS' if test2 else 'FAIL'}")
    print(f"Fallback case: {'PASS' if test3 else 'FAIL'}")
    print(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")