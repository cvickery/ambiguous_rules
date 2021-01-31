#! /usr/local/bin/python3

from collections import defaultdict, namedtuple
from pgconnection import PgConnection
from format_rules import _grade

conn = PgConnection()
rule_cursor = conn.cursor()
format_cursor = conn.cursor()

SrcSet = namedtuple('SrcSet', 'course_id offer_nbr min_gpa max_gpa course_status')
DstSet = namedtuple('DstSet', 'course_id, offer_nbr, is_bkcr')


def init_rule_info():
  """ Initialize structure for recording info about ambiguous rules.
      - source course set: course_id, offer_nbr, min_gpa, max_gpa, course_status
      - destination course set: course_id, offer_nbr, is_bkcr
  """
  return [set(), set()]


def key_order(key: str):
  parts = key.split(':')
  try:
    parts[3] = f'{int(parts[3]):04}'
  except ValueError as ve:
    print(key)
    return key
  return(':'.join(parts))


def format_rule(rule_id: int) -> str:
  """ Return string description of a transfer rule.
      By definition, only rules with ambiguities get here, so this is where information about the
      type of ambiguity is captured in the rule_info dict.
  """
  format_cursor.execute(f'select rule_key(id) from transfer_rules where id = {rule_id}')
  rule_key = format_cursor.fetchone().rule_key

  # Gather the set of sending courses for the rule
  format_cursor.execute(f"""
select  s.course_id, s.offer_nbr,
        s.discipline,
        s.catalog_number,
        min_gpa,
        max_gpa,
        c.course_status
  from source_courses s, cuny_courses c
  where s.rule_id = {rule_id}
    and c.course_id = s.course_id
    and c.offer_nbr = s.offer_nbr
                        """)
  # You are here: need add each sending course to rule_info[rule_key][0]
  rows = format_cursor.fetchall()
  for row in rows:
    rule_info[rule_key][0].add row
    # This is bogus:
    returnVal = ' and '.join([f'{_grade(r.min_gpa, r.max_gpa)} {r.discipline} {r.catalog_number} '
                            f'[{r.course_id:06} {r.course_status}]'
                           for r in row])
  returnVal += ' => '

  # Gather the set of receiving courses for the rule
  format_cursor.execute(f"""
select d.course_id, d.discipline, d.catalog_number, c.course_status, c.attributes
  from destination_courses d, cuny_courses c
  where rule_id = {rule_id}
    and d.course_id = c.course_id
    and d.offer_nbr = c.offer_nbr
                        """)
  # You are here: need add each sending course to rule_info[rule_key][0]
  rows = format_cursor.fetchall()
  for row in rows:
    rule_info[rule_key][1].add(row)
  # This is bogus
  for course in format_cursor.fetchall():
    if 'BKCR' in course.attributes:
      rule_info[rule_key][3] += 1
    courses.append(f'{course.discipline} {course.catalog_number} [{course.course_id:06} '
                   f'{course.course_status}]')
  returnVal += ' and '.join(courses)
  return returnVal


if __name__ == '__main__':

  rule_info = defaultdict(init_rule_info)
  course_rules = defaultdict(set)
  rule_cursor.execute("""
-- Get source courses that appear in multiple rules for the same destination institution.
select s1.course_id, s1.offer_nbr, s1.discipline, s1.catalog_number, c.course_status,
       s1.min_gpa as min_1, s1.max_gpa as max_1,
       r1.id as r1_id, rule_key(r1.id) as key_1, r1.priority as priority_1,
       s2.min_gpa as min_2, s2.max_gpa as max_2,
       r2.id as r2_id, rule_key(r2.id) as key_2, r2.priority as priority_2
  from source_courses s1, source_courses s2, transfer_rules r1, transfer_rules r2,cuny_courses c
  where s1.course_id = s2.course_id
    and s1.offer_nbr = s2.offer_nbr
    and s1.course_id = c.course_id
    and s1.rule_id = r1.id
    and s2.rule_id = r2.id
    and r1.id < r2.id
    and r1.destination_institution = r2.destination_institution
  order by course_id
                 """)

  # Full report in CSV format of all courses that appear in more than one rule having ambiguous
  # criteria for selecting the most-appropriate rule.
  with open('./min-max_overlap.csv', 'w') as mmo_file:
    print('course_id,course,min_1,max_1,rule 1,min_2,max_2,rule 2', file=mmo_file)
    for row in rule_cursor.fetchall():
      course = (row.course_id, row.offer_nbr)
      if row.priority_1 == row.priority_2 and (row.max_1 > row.min_2 or row.max_2 > row.min_1):
        if row.r2_id in course_rules[row.course_id] and row.r2_id in course_rules[row.course_id]:
          continue
        course_rules[course].add(row.r1_id)
        course_rules[course].add(row.r2_id)
        text_1 = format_rule(row.r1_id)
        text_2 = format_rule(row.r2_id)
        print(f'[{row.course_id:06}.{row.offer_nbr} {row.course_status}], '
              f'{row.discipline} {row.catalog_number},'
              f'{row.min_1}, {row.max_1}, {row.key_1}: {text_1}, '
              f'{row.min_2}, {row.max_2}, {row.key_2}: {text_2}', file=mmo_file)

  with open('./rule_report.csv', 'w') as report_file:
    print('Rule, Num Cases, Num Sending, Num Receiving, Num BKCR', file=report_file)
    keys = sorted(rule_info.keys(), key=key_order)
    for key in keys:
      data = ','.join([f'{v}' for v in rule_info[key]])
      print(f'{key}, {data}', file=report_file)
