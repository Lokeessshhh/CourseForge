"""
Script to manually unlock coding tests and generate sample data for testing.
Run this with: python manage.py shell < scripts/unlock_coding_tests.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.courses.models import Course, WeekPlan, CodingTest, CodingTestAttempt
from django.utils import timezone
import uuid

COURSE_ID = "58852d78-739d-488b-9259-67b5f7859459"
WEEK_NUMBER = 1

print("=" * 60)
print("UNLOCKING CODING TESTS FOR TESTING")
print("=" * 60)

try:
    # Get course and week
    course = Course.objects.get(id=COURSE_ID)
    week = course.weeks.get(week_number=WEEK_NUMBER)
    
    print(f"\n Found course: {course.course_name}")
    print(f" Found week: {WEEK_NUMBER}")
    
    # Unlock coding tests
    week.coding_tests_generated = True
    week.coding_test_1_unlocked = True
    week.coding_test_2_unlocked = True
    week.test_unlocked = True  # Also ensure weekly test is unlocked
    week.save(update_fields=[
        'coding_tests_generated',
        'coding_test_1_unlocked', 
        'coding_test_2_unlocked',
        'test_unlocked'
    ])
    
    print("\n WeekPlan updated:")
    print(f"  - coding_tests_generated: {week.coding_tests_generated}")
    print(f"  - coding_test_1_unlocked: {week.coding_test_1_unlocked}")
    print(f"  - coding_test_2_unlocked: {week.coding_test_2_unlocked}")
    print(f"  - test_unlocked: {week.test_unlocked}")
    
    # Create or update Coding Test 1
    coding_test_1, created = CodingTest.objects.get_or_create(
        course=course,
        week_number=WEEK_NUMBER,
        test_number=1,
        defaults={
            'total_problems': 2,
            'problems': [
                {
                    "problem_number": 1,
                    "title": "Two Sum",
                    "description": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.",
                    "difficulty": "easy",
                    "starter_code": "def twoSum(nums, target):\n    # Write your code here\n    pass",
                    "test_cases": [
                        {
                            "input": "nums = [2,7,11,15], target = 9",
                            "expected_output": "[0,1]"
                        },
                        {
                            "input": "nums = [3,2,4], target = 6",
                            "expected_output": "[1,2]"
                        },
                        {
                            "input": "nums = [3,3], target = 6",
                            "expected_output": "[0,1]"
                        }
                    ]
                },
                {
                    "problem_number": 2,
                    "title": "Reverse String",
                    "description": "Write a function that reverses a string. The input string is given as an array of characters s.\n\nYou must do this by modifying the input array in-place with O(1) extra memory.",
                    "difficulty": "easy",
                    "starter_code": "def reverseString(s):\n    # Write your code here\n    # Modify s in-place, do not return anything\n    pass",
                    "test_cases": [
                        {
                            "input": "s = ['h','e','l','l','o']",
                            "expected_output": "['o','l','l','e','h']"
                        },
                        {
                            "input": "s = ['H','a','n','n','a','h']",
                            "expected_output": "['h','a','n','n','a','H']"
                        }
                    ]
                }
            ]
        }
    )
    
    if not created:
        # Update existing test
        coding_test_1.problems = [
            {
                "problem_number": 1,
                "title": "Two Sum",
                "description": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.",
                "difficulty": "easy",
                "starter_code": "def twoSum(nums, target):\n    # Write your code here\n    pass",
                "test_cases": [
                    {
                        "input": "nums = [2,7,11,15], target = 9",
                        "expected_output": "[0,1]"
                    },
                    {
                        "input": "nums = [3,2,4], target = 6",
                        "expected_output": "[1,2]"
                    },
                    {
                        "input": "nums = [3,3], target = 6",
                        "expected_output": "[0,1]"
                    }
                ]
            },
            {
                "problem_number": 2,
                "title": "Reverse String",
                "description": "Write a function that reverses a string. The input string is given as an array of characters s.\n\nYou must do this by modifying the input array in-place with O(1) extra memory.",
                "difficulty": "easy",
                "starter_code": "def reverseString(s):\n    # Write your code here\n    # Modify s in-place, do not return anything\n    pass",
                "test_cases": [
                    {
                        "input": "s = ['h','e','l','l','o']",
                        "expected_output": "['o','l','l','e','h']"
                    },
                    {
                        "input": "s = ['H','a','n','n','a','h']",
                        "expected_output": "['h','a','n','n','a','H']"
                    }
                ]
            }
        ]
        coding_test_1.save(update_fields=['problems'])
        print("\n Coding Test 1 updated with sample problems")
    else:
        print("\n Coding Test 1 created with sample problems")
    
    # Create or update Coding Test 2
    coding_test_2, created = CodingTest.objects.get_or_create(
        course=course,
        week_number=WEEK_NUMBER,
        test_number=2,
        defaults={
            'total_problems': 2,
            'problems': [
                {
                    "problem_number": 1,
                    "title": "Palindrome Number",
                    "description": "Given an integer x, return true if x is a palindrome, and false otherwise.\n\nAn integer is a palindrome when it reads the same forward and backward.",
                    "difficulty": "easy",
                    "starter_code": "def isPalindrome(x):\n    # Write your code here\n    pass",
                    "test_cases": [
                        {
                            "input": "x = 121",
                            "expected_output": "True"
                        },
                        {
                            "input": "x = -121",
                            "expected_output": "False"
                        },
                        {
                            "input": "x = 10",
                            "expected_output": "False"
                        }
                    ]
                },
                {
                    "problem_number": 2,
                    "title": "FizzBuzz",
                    "description": "Given an integer n, return a string array answer (1-indexed) where:\n- answer[i] == 'FizzBuzz' if i is divisible by 3 and 5\n- answer[i] == 'Fizz' if i is divisible by 3\n- answer[i] == 'Buzz' if i is divisible by 5\n- answer[i] == i (as a string) if none of the above conditions are true",
                    "difficulty": "medium",
                    "starter_code": "def fizzBuzz(n):\n    # Write your code here\n    pass",
                    "test_cases": [
                        {
                            "input": "n = 3",
                            "expected_output": "['1','2','Fizz']"
                        },
                        {
                            "input": "n = 5",
                            "expected_output": "['1','2','Fizz','4','Buzz']"
                        },
                        {
                            "input": "n = 15",
                            "expected_output": "['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz']"
                        }
                    ]
                }
            ]
        }
    )
    
    if not created:
        # Update existing test
        coding_test_2.problems = [
            {
                "problem_number": 1,
                "title": "Palindrome Number",
                "description": "Given an integer x, return true if x is a palindrome, and false otherwise.\n\nAn integer is a palindrome when it reads the same forward and backward.",
                "difficulty": "easy",
                "starter_code": "def isPalindrome(x):\n    # Write your code here\n    pass",
                "test_cases": [
                    {
                        "input": "x = 121",
                        "expected_output": "True"
                    },
                    {
                        "input": "x = -121",
                        "expected_output": "False"
                    },
                    {
                        "input": "x = 10",
                        "expected_output": "False"
                    }
                ]
            },
            {
                "problem_number": 2,
                "title": "FizzBuzz",
                "description": "Given an integer n, return a string array answer (1-indexed) where:\n- answer[i] == 'FizzBuzz' if i is divisible by 3 and 5\n- answer[i] == 'Fizz' if i is divisible by 3\n- answer[i] == 'Buzz' if i is divisible by 5\n- answer[i] == i (as a string) if none of the above conditions are true",
                "difficulty": "medium",
                "starter_code": "def fizzBuzz(n):\n    # Write your code here\n    pass",
                "test_cases": [
                    {
                        "input": "n = 3",
                        "expected_output": "['1','2','Fizz']"
                    },
                    {
                        "input": "n = 5",
                        "expected_output": "['1','2','Fizz','4','Buzz']"
                    },
                    {
                        "input": "n = 15",
                        "expected_output": "['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz']"
                    }
                ]
            }
        ]
        coding_test_2.save(update_fields=['problems'])
        print(" Coding Test 2 updated with sample problems")
    else:
        print(" Coding Test 2 created with sample problems")
    
    print("\n" + "=" * 60)
    print("SUCCESS! Coding tests are now unlocked and ready to test.")
    print("=" * 60)
    print("\nYou can now visit:")
    print(f"  → Coding Test 1: http://localhost:3000/dashboard/courses/{COURSE_ID}/week/1/coding-test/1")
    print(f"  → Coding Test 2: http://localhost:3000/dashboard/courses/{COURSE_ID}/week/1/coding-test/2")
    print("\nSample Problems:")
    print("  Coding Test 1:")
    print("    1. Two Sum (Easy)")
    print("    2. Reverse String (Easy)")
    print("  Coding Test 2:")
    print("    1. Palindrome Number (Easy)")
    print("    2. FizzBuzz (Medium)")
    
except Course.DoesNotExist:
    print(f"\n ERROR: Course {COURSE_ID} not found!")
except WeekPlan.DoesNotExist:
    print(f"\n ERROR: Week {WEEK_NUMBER} not found in course!")
except Exception as e:
    print(f"\n ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
