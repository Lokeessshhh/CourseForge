from django.core.management.base import BaseCommand
from apps.courses.models import Course, WeekPlan, CodingTest
import json

class Command(BaseCommand):
    help = 'Generate sample coding tests for a course'

    def add_arguments(self, parser):
        parser.add_argument('course_id', type=str, help='Course UUID')
        parser.add_argument('week_number', type=int, help='Week number')

    def handle(self, *args, **options):
        course_id = options['course_id']
        week_number = options['week_number']

        self.stdout.write(self.style.SUCCESS(f'Generating coding tests for course {course_id}, week {week_number}'))

        try:
            course = Course.objects.get(id=course_id)
            week = course.weeks.get(week_number=week_number)

            # Unlock coding tests
            week.coding_tests_generated = True
            week.coding_test_1_unlocked = True
            week.coding_test_2_unlocked = True
            week.test_unlocked = True
            week.save(update_fields=[
                'coding_tests_generated',
                'coding_test_1_unlocked',
                'coding_test_2_unlocked',
                'test_unlocked'
            ])

            self.stdout.write(self.style.SUCCESS('✓ WeekPlan updated successfully'))

            # Create Coding Test 1
            coding_test_1, created = CodingTest.objects.get_or_create(
                course=course,
                week_number=week_number,
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
                                {"input": "nums = [2,7,11,15], target = 9", "expected_output": "[0,1]"},
                                {"input": "nums = [3,2,4], target = 6", "expected_output": "[1,2]"},
                                {"input": "nums = [3,3], target = 6", "expected_output": "[0,1]"}
                            ]
                        },
                        {
                            "problem_number": 2,
                            "title": "Reverse String",
                            "description": "Write a function that reverses a string. The input string is given as an array of characters s.\n\nYou must do this by modifying the input array in-place with O(1) extra memory.",
                            "difficulty": "easy",
                            "starter_code": "def reverseString(s):\n    # Write your code here\n    # Modify s in-place, do not return anything\n    pass",
                            "test_cases": [
                                {"input": "s = ['h','e','l','l','o']", "expected_output": "['o','l','l','e','h']"},
                                {"input": "s = ['H','a','n','n','a','h']", "expected_output": "['h','a','n','n','a','H']"}
                            ]
                        }
                    ]
                }
            )

            if not created:
                self.stdout.write(self.style.WARNING('⚠ Coding Test 1 already exists, skipping'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Coding Test 1 created'))

            # Create Coding Test 2
            coding_test_2, created = CodingTest.objects.get_or_create(
                course=course,
                week_number=week_number,
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
                                {"input": "x = 121", "expected_output": "True"},
                                {"input": "x = -121", "expected_output": "False"},
                                {"input": "x = 10", "expected_output": "False"}
                            ]
                        },
                        {
                            "problem_number": 2,
                            "title": "FizzBuzz",
                            "description": "Given an integer n, return a string array answer (1-indexed) where:\n- answer[i] == 'FizzBuzz' if i is divisible by 3 and 5\n- answer[i] == 'Fizz' if i is divisible by 3\n- answer[i] == 'Buzz' if i is divisible by 5\n- answer[i] == i (as a string) if none of the above conditions are true",
                            "difficulty": "medium",
                            "starter_code": "def fizzBuzz(n):\n    # Write your code here\n    pass",
                            "test_cases": [
                                {"input": "n = 3", "expected_output": "['1','2','Fizz']"},
                                {"input": "n = 5", "expected_output": "['1','2','Fizz','4','Buzz']"},
                                {"input": "n = 15", "expected_output": "['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz']"}
                            ]
                        }
                    ]
                }
            )

            if not created:
                self.stdout.write(self.style.WARNING('⚠ Coding Test 2 already exists, skipping'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Coding Test 2 created'))

            self.stdout.write(self.style.SUCCESS('\n✅ All done! You can now access the coding tests.'))
            self.stdout.write(self.style.SUCCESS(f'   Test 1: http://localhost:3000/dashboard/courses/{course_id}/week/{week_number}/coding-test/1'))
            self.stdout.write(self.style.SUCCESS(f'   Test 2: http://localhost:3000/dashboard/courses/{course_id}/week/{week_number}/coding-test/2'))

        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Course {course_id} not found'))
        except WeekPlan.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Week {week_number} not found in course'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            import traceback
            traceback.print_exc()
