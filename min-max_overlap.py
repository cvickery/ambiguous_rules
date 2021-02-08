#! /usr/local/bin/python3

import argparse

from collections import defaultdict, namedtuple
from pgconnection import PgConnection
from format_rules import _grade

conn = PgConnection()
first_cursor = conn.cursor()  # Finds courses with ambiguous courses
format_cursor = conn.cursor()  # Used to format a rule
second_cursor = conn.cursor()  #

SrcCourse = namedtuple('SrcCourse', 'course_id offer_nbr discipline catalog_number '
                       'min_gpa max_gpa designation course_status')
DstCourse = namedtuple('DstCourse', 'course_id offer_nbr is_msg is_bkcr course_status')
RuleInfo = namedtuple('RuleInfo', 'src_courses dst_courses text')


def init_rule_info():
  """ Initialize structure for recording info about ambiguous rules as a tuple of two sets.
      Set[0] is SrcCourses; set[1] is DstCourses
  """
  return RuleInfo._make([set(), set(), []])


def key_order(key: str):
  parts = key.split(':')
  try:
    parts[3] = f'{int(parts[3]):04}'
  except ValueError as ve:
    print(key)
    return key
  return(':'.join(parts))


def format_range(course, ambiguous_low, ambiguous_high):
  low = min(ambiguous_low, ambiguous_high)
  high = max(ambiguous_low, ambiguous_high)
  range = _grade(low, high)
  preposition = ' ' if range == 'Pass' else ' in '
  return f'  Grade ambiguity: {range}{preposition}{course.discipline} {course.catalog_number}'


def format_rule(rule_id: int) -> str:
  """ Return string description of a transfer rule.
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
        c.designation,
        c.course_status
  from source_courses s, cuny_courses c
  where s.rule_id = {rule_id}
    and c.course_id = s.course_id
    and c.offer_nbr = s.offer_nbr
  order by s.discipline, numeric_part(s.catalog_number)
                        """)
  courses = format_cursor.fetchall()
  for course in courses:
    # print(SrcCourse._make([course.course_id,
    rule_info[rule_key].src_courses.add(SrcCourse._make([course.course_id,
                                                         course.offer_nbr,
                                                         course.discipline,
                                                         course.catalog_number,
                                                         course.min_gpa,
                                                         course.max_gpa,
                                                         course.designation,
                                                         course.course_status]))

  returnVal = ' and '.join([f'{_grade(c.min_gpa, c.max_gpa)} {c.discipline} {c.catalog_number} '
                            f'[{c.course_id:06}.{course.offer_nbr} {c.course_status}]'
                            for c in courses])
  returnVal += ' => '

  # Gather the set of receiving courses for the rule
  format_cursor.execute(f"""
select  d.course_id,
        d.offer_nbr,
        d.discipline,
        d.catalog_number,
        c.designation,
        c.attributes,
        c.course_status
  from destination_courses d, cuny_courses c
  where rule_id = {rule_id}
    and d.course_id = c.course_id
    and d.offer_nbr = c.offer_nbr
                        """)
  dest_list = []
  courses = format_cursor.fetchall()
  # Add each receiving course to rule_info[rule_key][1]
  for course in courses:
    # print((DstCourse._make([course.course_id,
    rule_info[rule_key].dst_courses.add(DstCourse._make([course.course_id,
                                                         course.offer_nbr,
                                                         (course.designation == 'MLA'
                                                          or course.designation == 'MNL'),
                                                         'BKCR' in course.attributes,
                                                        course.course_status]))
    dest_list.append(f'{course.discipline} {course.catalog_number} '
                     f'[{course.course_id:06}.{course.offer_nbr} {course.course_status}]')
  returnVal += ' and '.join(dest_list)
  rule_info[rule_key].text.append(returnVal)
  return returnVal


if __name__ == '__main__':

  parser = argparse.ArgumentParser(description='Test DGW Parser')
  parser.add_argument('-d', '--debug', action='store_true', default=False)
  parser.add_argument('-p', '--progress', action='store_true', default=False)
  args = parser.parse_args()

  rule_info = defaultdict(init_rule_info)
  ambiguous_pairs = []
  course_rules = defaultdict(set)

  if args.progress:
    print('Start DB Query')
  first_cursor.execute("""
-- Get source courses that appear in pairs of rules for the same destination institution.
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

  # Filter for cases where there is no way to tell which rule should apply.
  with open('./min-max_overlap.csv', 'w') as mmo_file:
    print('course_id,course,min_1,max_1,rule 1,min_2,max_2,rule 2', file=mmo_file)
    m = 0
    n = first_cursor.rowcount
    for row in first_cursor.fetchall():
      if args.progress:
        if m == 0:
          print('Build rule pairs')
        m += 1
        print(f' {m:06,}/{n:06,}\r', end='')
      course = (row.course_id, row.offer_nbr)
      if row.priority_1 == row.priority_2 and (row.max_1 > row.min_2 or row.max_2 > row.min_1):
        # Update info for this pair of rules
        ambiguous_pairs.append((row.key_1, row.key_2))
        # Add row for this course to CSV report
        if row.r2_id in course_rules[row.course_id] and row.r2_id in course_rules[row.course_id]:
          # Skip rules already seen for this course
          continue
        course_rules[course].add(row.r1_id)
        course_rules[course].add(row.r2_id)
        text_1 = format_rule(row.r1_id)
        text_2 = format_rule(row.r2_id)
        print(f'[{row.course_id:06}.{row.offer_nbr} {row.course_status}], '
              f'{row.discipline} {row.catalog_number},'
              f'{row.min_1}, {row.max_1}, {row.key_1}: {text_1}, '
              f'{row.min_2}, {row.max_2}, {row.key_2}: {text_2}', file=mmo_file)

  # Generate Report
  """ For each pair of rules that includes at least one course ambiguity, report:
         -  If the rules are redundant, and if so tell whether the difference is in the component
            subject area, the group number, or both.
         -  If the rules are not redundant:
            - List all ambiguous courses and their overlapping grade ranges
         -  - For each receiving course is it msg; is it BKCR; indicate which rule (or rules) it
              belongs to.
  """
  m = 0
  n = len(ambiguous_pairs)
  with open('./rule_report.txt', 'w') as report_file:
    for pair in ambiguous_pairs:
      if args.progress:
        if m == 0:
          print('Analyze rule pairs')
        m += 1
        print(f' {m:06,}/{n:06,}\r', end='')

      # Tell what rule-pair is being reported on
      print(f'\n{pair[0]:24} {rule_info[pair[0]].text[0]}\n'
            f'{pair[1]:24} {rule_info[pair[1]].text[0]}', file=report_file)

      # What sending courses are problematic, and what is the range of overlap?
      for course_1 in rule_info[pair[0]].src_courses:
        for course_2 in rule_info[pair[1]].src_courses:
          if (course_1.course_id, course_1.offer_nbr) == (course_2.course_id, course_2.offer_nbr):
            if course_1.max_gpa > course_2.min_gpa or course_2.max_gpa > course_1.min_gpa:
              ambiguous_low = max(course_1.min_gpa, course_2.min_gpa)
              ambiguous_high = min(course_1.max_gpa, course_2.max_gpa)
              print(format_range(course_1, ambiguous_low, ambiguous_high), file=report_file)

      # Are the source and destination course sets the same for the two rules?
      source_1 = set([(rule.course_id, rule.offer_nbr) for rule in rule_info[pair[0]].src_courses])
      source_2 = set([(rule.course_id, rule.offer_nbr) for rule in rule_info[pair[1]].src_courses])
      dest_1 = set([(rule.course_id, rule.offer_nbr) for rule in rule_info[pair[0]].dst_courses])
      dest_2 = set([(rule.course_id, rule.offer_nbr) for rule in rule_info[pair[1]].dst_courses])
      if source_1 == source_2 and dest_1 == dest_2:
        same_comp = 'same' if pair[0].split(':')[2] == pair[1].split(':')[2] else 'different'
        print(f'  Same sending and receiving courses with {same_comp} component subject areas',
              file=report_file)
      elif source_1 == source_2:
        print(f'  Same sending courses; different receiving courses', file=report_file)
      elif dest_1 == dest_2:
        print(f'  Different sending courses; same receiving courses', file=report_file)
      else:
        print(f'  Different sending and receiving courses', file=report_file)

      # Are receiving courses BKCR and/or MSG?
      all_blanket_1 = True
      all_message_1 = True
      any_blanket_1 = False
      any_message_1 = False
      for course in rule_info[pair[0]].dst_courses:
        if course.is_msg:
          any_message_1 = True
        else:
          all_message_1 = False
        if course.is_bkcr:
          any_blanket_1 = True
        else:
          all_blanket_1 = False

      all_blanket_2 = True
      all_message_2 = True
      any_blanket_2 = False
      any_message_2 = False
      for course in rule_info[pair[1]].dst_courses:
        if course.is_msg:
          any_message_2 = True
        else:
          all_message_2 = False
        if course.is_bkcr:
          any_blanket_2 = True
        else:
          all_blanket_2 = False

      # So many possibilities...
      if all_blanket_1 and all_blanket_2:
        print(f'  Both rules are all BKCR', file=report_file)
      elif all_blanket_1:
        if any_blanket_2:
          print(f'  First rule is all BKCR; Second rule is part BKCR', file=report_file)
        else:
          print(f'  First rule is all BKCR; Second rule is not BKCR', file=report_file)
      elif all_blanket_2:
        if any_blanket_1:
          print(f'  First rule is part BKCR; Second rule is all BKCR', file=report_file)
        else:
          print(f'  First rule is not BKCR; Second rule is all BKCR; ', file=report_file)
      else:
        print(f'  Neither rule is BKCR', file=report_file)

      if all_message_1 and all_message_2:
        print(f'  Both rules are all MSG', file=report_file)
      elif all_message_1:
        if any_message_2:
          print(f'  First rule is all MSG; Second rule is part MSG', file=report_file)
        else:
          print(f'  First rule is all MSG; Second rule is not MSG', file=report_file)
      elif all_message_2:
        if any_message_1:
          print(f'  First rule is part MSG; Second rule is all MSG', file=report_file)
        else:
          print(f'  First rule is not MSG; Second rule is all MSG; ', file=report_file)
      else:
        print(f'  Neither rule is MSG', file=report_file)
