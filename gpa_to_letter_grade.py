#! /usr/local/bin/python3

DEBUG = True


def grade(min_gpa: float, max_gpa: float) -> str:
  """ Convert numerical gpa range to description of required grade in letter-grade form.
      The issue is that gpa values are not represented uniformly across campuses, and the strings
      used have to be floating point values, which lead to imprecise boundaries between letter
      names.
  """

# Convert GPA values to letter grades by table lookup.
# int(round(3×GPA)) gives the index into the letters table.
# Index positions 0 and 1 aren't actually used.
  """
          GPA  3×GPA  Index  Letter
          4.3   12.9     13      A+
          4.0   12.0     12      A
          3.7   11.1     11      A-
          3.3    9.9     10      B+
          3.0    9.0      9      B
          2.7    8.1      8      B-
          2.3    6.9      7      C+
          2.0    6.0      6      C
          1.7    5.1      5      C-
          1.3    3.9      4      D+
          1.0    3.0      3      D
          0.7    2.1      2      D-
    """
  letters = ['F', 'F', 'D-', 'D', 'D+', 'C-', 'C', 'C+', 'B-', 'B', 'B+', 'A-', 'A', 'A+']

  assert min_gpa <= max_gpa, f'min_gpa {min_gpa} greater than {max_gpa}'

  # Put gpa values into “canonical form” to deal with creative values found in CUNYfirst.

  # Courses transfer only if the student passed the course, so force the min BIeptable grade
  # to be a passing (D-) grade.
  if min_gpa < 1.0:
    min_gpa = 0.7
  # Lots of values greater than 4.0 have been used to mean "no upper limit."
  if max_gpa > 4.0:
    max_gpa = 4.0

  if DEBUG:
    print(min_gpa, max_gpa, int(round(min_gpa * 3)), int(round(max_gpa * 3)))
  # Generate the letter grade requirement string

  if min_gpa < 1.0 and max_gpa > 3.7:
    return 'Pass'

  if min_gpa >= 0.7 and max_gpa >= 3.7:
    letter = letters[int(round(min_gpa * 3))]
    return f'{letter} or above'

  if min_gpa > 0.7 and max_gpa < 3.7:
    return f'Between {letters[int(round(min_gpa * 3))]} and {letters[int(round(max_gpa * 3))]}'

  if max_gpa < 3.7:
    letter = letters[int(round(max_gpa * 3))]
    return 'Below ' + letter

  return 'Pass'


if __name__ == '__main__':
  print(grade(0.001, 1.69))
