#! /usr/local/bin/python3

from collections import namedtuple
from pgconnection import PgConnection
from format_rules import _grade


# _rule_key()
# -------------------------------------------------------------------------------------------------
def _rule_key(row) -> str:
  """
  """
  return (f'{row.source_institution[0:3]}-'
          f'{row.destination_institution[0:3]}-'
          f'{row.subject_area}-'
          f'{row.group_number}')


if __name__ == '__main__':

  source_institution = 'QCC01'
  destination_institution = 'QNS01'
  subject_area = 'BI'

  conn = PgConnection()
  rule_cursor = conn.cursor()
  source_cursor = conn.cursor()
  destination_cursor = conn.cursor()
  with open('./by_rule.csv', 'w') as by_rule:
    print('Rule, Sending, Receiving', file=by_rule)
    # Working example: Physics courses at QCC to QNS
    rule_cursor.execute(f"""
    select * from transfer_rules
    where source_institution = '{source_institution}'
      and destination_institution = '{destination_institution}'
      and subject_area = '{subject_area}'
    order by group_number
                   """)
    for rule in rule_cursor.fetchall():
      source_cursor.execute(f"""
  select * from source_courses where rule_id = {rule.id}
                            """)
      source_courses = ' and '.join([f'{_grade(sc.min_gpa, sc.max_gpa)} in '
                                    f'{sc.discipline} {sc.catalog_number} '
                                     for sc in source_cursor.fetchall()])

      destination_cursor.execute(f"""
  select * from destination_courses where rule_id = {rule.id}
                                 """)
      destination_courses = ' and '.join([f'{dc.transfer_credits:0.1f} cr. '
                                          f'{dc.discipline} {dc.catalog_number}'
                                         for dc in destination_cursor.fetchall()])
      print(f'{_rule_key(rule)},{source_courses},{destination_courses}', file=by_rule)

  with open('./by_course.csv', 'w') as by_course:
    print('Course, Grade, Rule(priority)', file=by_course)
    rule_cursor.execute(f"""
select s.discipline, s.catalog_number, s.min_gpa, s.max_gpa,
       rule_key(s.rule_id), r.priority
from source_courses s, transfer_rules r
where r.id = s.rule_id
and r.source_institution = '{source_institution}'
and r.destination_institution = '{destination_institution}'
and r.subject_area = '{subject_area}'
order by catalog_number, priority
                        """)
    Prev_Course = namedtuple('Prev_Course', 'discipline, catalog_number, grade_str')
    prev_course = None
    for course in rule_cursor.fetchall():
      if prev_course is None:
        prev_course = Prev_Course._make([course.discipline, course.catalog_number,
                                        _grade(course.min_gpa, course.max_gpa)])
        keys_list = [f'{course.rule_key}({course.priority})']

      if course.catalog_number != prev_course.catalog_number:
        keys_str = ' '.join(keys_list)
        print(f'{prev_course.discipline} {prev_course.catalog_number},'
              f'{prev_course.grade_str},'
              f'{keys_str}', file=by_course)
        keys_list = [f'{course.rule_key}({course.priority})']
        prev_course = Prev_Course._make([course.discipline, course.catalog_number,
                                        _grade(course.min_gpa, course.max_gpa)])
      else:
        keys_list.append(f'{course.rule_key}({course.priority})')
