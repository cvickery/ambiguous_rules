#! /usr/local/bin/python3
""" Generate a report of ambiguous transfer rules.
"""
import argparse
import psycopg
import sys

from collections import defaultdict, namedtuple
from datetime import date
from psycopg.rows import namedtuple_row
from format_rules import _grade

conn = psycopg.connect('dbname=cuny_curriculum')
# Cursor to find potentially ambiguous rules
first_cursor = conn.cursor(row_factory=namedtuple_row)
# Cursor to lookup source_courses and, later, destination courses
second_cursor = conn.cursor(row_factory=namedtuple_row)

Rule = namedtuple('Rule', 'id key')


# key_order()
# -------------------------------------------------------------------------------------------------
def key_order(key: str):
  """ Sort order for rule_keys as recv:send:subj:int(group)
  """
  parts = key.split(':')
  try:
    parts[3] = f'{int(parts[3]):04}'
  except ValueError:
    print(f'Bogus rule_key: {key}', file=sys.stderr)
    return key
  return f'{parts[1]}:{parts[0]}:{parts[2]}:{parts[3]}'


# format_range()
# -------------------------------------------------------------------------------------------------
def format_range(course, ambiguous_low, ambiguous_high):
  """ Generate grade ambiguity string, showing the range of overlapping grades for a course.
  """
  low = min(ambiguous_low, ambiguous_high)
  high = max(ambiguous_low, ambiguous_high)
  range = _grade(low, high)
  preposition = ' ' if range == 'Pass' else ' in '
  return f'{range}{preposition}{course.discipline} {course.catalog_number}'


# format_rules()
# -------------------------------------------------------------------------------------------------
def format_rules(pair: tuple, sending_courses: tuple) -> list:
  """ Generate list of additional info for two rules
      The info for each rule consists of:
        The textual representations of the two rules
        Lists of receiving courses with their designations, attributes, and course_statuses for the
        two rules.
  """
  assert len(pair) == 2
  rules_info = [dict(), dict()]
  rules_info[0]['text'] = ' and '.join([f'{_grade(c.min_gpa, c.max_gpa)} {c.discipline} '
                                        f'{c.catalog_number} [{c.course_id:06}.'
                                        f'{c.offer_nbr} {c.course_status}]'
                                        for c in sending_courses[0]]) + ' => '
  rules_info[1]['text'] = ' and '.join([f'{_grade(c.min_gpa, c.max_gpa)} {c.discipline} '
                                        f'{c.catalog_number} [{c.course_id:06}.'
                                        f'{c.offer_nbr} {c.course_status}]'
                                        for c in sending_courses[1]]) + ' => '

  # Gather the set of receiving courses for the two rules
  for index in range(2):
    second_cursor.execute(f"""
select  d.course_id,
        d.offer_nbr,
        d.discipline,
        d.catalog_number,
        c.designation in ('MLA', 'MNL') as is_mesg,
        c.attributes ~ 'BKCR' as is_bkcr,
        c.course_status
  from destination_courses d, cuny_courses c
  where rule_id = {pair[index].id}
    and d.course_id = c.course_id
    and d.offer_nbr = c.offer_nbr
                        """)
    dest_courses = second_cursor.fetchall()
    rules_info[index]['dest_courses'] = dest_courses
    rules_info[index]['text'] += ' and '.join([f'{course.discipline} '
                                               f'{course.catalog_number} '
                                               f'[{course.course_id:06}.'
                                               f'{course.offer_nbr} '
                                               f'{course.course_status}]'
                                               for course in dest_courses])
  return rules_info


if __name__ == '__main__':

  parser = argparse.ArgumentParser(description='Generate ambiguous rules report')
  parser.add_argument('-d', '--debug', action='store_true', default=False)
  parser.add_argument('-p', '--progress', action='store_true', default=False)
  args = parser.parse_args()

  with psycopg.connect('dbname=cuny_curriculum') as conn:
    # For potentially ambiguous rules
    with conn.cursor(row_factory=namedtuple_row) as first_cursor:
      # For course lookups
      with conn.cursor(row_factory=namedtuple_row) as second_cursor:

        if args.progress:
          print('Lookup problem rules', file=sys.stderr)
        first_cursor.execute("""
      -- Look up potential ambiguities: cases where the only way to tell which rule applies would be
      -- a difference in grade requirements.

      select r1.id as id_1, r1.rule_key as key_1,
             r2.id as id_2, r2.rule_key as key_2,
             r1.sending_courses,
             r1.receiving_courses as receiving_1,
             r2.receiving_courses as receiving_2
      from transfer_rules r1, transfer_rules r2
      where r1.id < r2.id
      and r1.destination_institution = r2.destination_institution
      and r1.sending_courses = r2.sending_courses
      and r1.priority = r2.priority
      order by r1.rule_key, r2.rule_key

      """)

        # Lookup courses involved and generate string represenation of the rules
        m = 0
        n = first_cursor.rowcount
        ambiguous_pairs = set()   # Rule_key pairs
        source_info = defaultdict(tuple)   # Pair of source course lookups indexed by rule_key pair

        for row in first_cursor.fetchall():
          if args.progress:
            if m == 0:
              print('Format rule pairs', file=sys.stderr)
            m += 1
            print(f' {m:06,}/{n:06,}\r', end='', file=sys.stderr)

          # Lookup the sending course info for the two rules.
          second_cursor.execute(f"""
      select s.*, c.course_status, c.designation, c.attributes
        from source_courses s, cuny_courses c
       where rule_id = {row.id_1}
         and c.course_id = s.course_id
         and c.offer_nbr = s.offer_nbr
        order by course_id, offer_nbr
      """)
          r1_sending_courses = second_cursor.fetchall()

          second_cursor.execute(f"""
      select s.*, c.course_status, c.designation, c.attributes
        from source_courses s, cuny_courses c
       where rule_id = {row.id_2}
         and c.course_id = s.course_id
         and c.offer_nbr = s.offer_nbr
        order by course_id, offer_nbr
      """)
          r2_sending_courses = second_cursor.fetchall()

          # The rules are ambiguous if one or more courses have overlapping grade requirements.
          assert len(r1_sending_courses) == len(r2_sending_courses)
          for index in range(len(r1_sending_courses)):
            assert (r1_sending_courses[index].course_id == r2_sending_courses[index].course_id
                    and r1_sending_courses[index].offer_nbr == r2_sending_courses[index].offer_nbr)

            # Test for not not overlapping
            if not ((r1_sending_courses[index].max_gpa < r2_sending_courses[index].min_gpa) or
                    (r2_sending_courses[index].max_gpa < r1_sending_courses[index].min_gpa)):
              pair = (Rule._make([row.id_1, row.key_1]), Rule._make([row.id_2, row.key_2]))
              ambiguous_pairs.add(pair)
              source_info[pair] = (r1_sending_courses, r2_sending_courses)
              break   # No need to continue once one ambiguity is found

        # Generate Report
        """ For each pair of rules that includes at least one course ambiguity, report:
               -  If the rules are redundant, and if so tell whether the difference is in the
               -  component subject area, the group number, or both.
               -  If the rules are not redundant:
                  - List all ambiguous courses and their overlapping grade ranges
                  - For each receiving course is it msg; is it BKCR; indicate which rule (or rules)
                    it belongs to.
        """
        m = 0
        n = len(ambiguous_pairs)
        today = date.today()
        with open(f'./reports/rules_report_{today}.txt', 'w') as report_file:
          # Process ambiguities in receiving college order
          for pair in sorted(ambiguous_pairs, key=lambda x: key_order(x[0].key)):
            if args.progress:
              if m == 0:
                print('Analyze rule pairs')
              m += 1
              print(f' {m:06,}/{n:06,}\r', end='', file=sys.stderr)

            # Fill out the information for the rule
            rules_info = format_rules(pair, source_info[pair])

            # Tell what rule-pair is being reported on
            print(f'\n{pair[0].key:24} {rules_info[0]["text"]}\n'
                  f'{pair[1].key:24} {rules_info[1]["text"]}', file=report_file)

            # What sending courses are problematic, and what is the range of overlap?
            ambiguities = set()
            for course_1 in source_info[pair][0]:
              for course_2 in source_info[pair][1]:
                if course_1.rule_id in [1443687, 1441399]:
                  breakpoint()
                if not (course_1.min_gpa > course_2.max_gpa or course_2.min_gpa > course_1.max_gpa):
                  ambiguous_low = max(course_1.min_gpa, course_2.min_gpa)
                  ambiguous_high = min(course_1.max_gpa, course_2.max_gpa)
                  # Check for cross-listing possibilities
                  first_cursor.execute(f"""
      select offer_nbr, discipline, catalog_number, course_status
        from cuny_courses
       where course_id = {course_1.course_id}
         and offer_nbr != {course_1.offer_nbr}
      """)
                  if first_cursor.rowcount > 0:
                    cross_listed = ' (' + '; '.join([f'[{course_1.course_id:06}.{c.offer_nbr} = '
                                                     f'{c.discipline} {c.catalog_number} '
                                                     f'{c.course_status}]'
                                                     for c in first_cursor.fetchall()]) + ')'
                  else:
                    cross_listed = ''
                  ambiguities.add(format_range(course_1,
                                               ambiguous_low, ambiguous_high) + cross_listed)
            if len(ambiguities) == 1:
              print(f'  Grade ambiguity: {ambiguities.pop()}', file=report_file)
            else:
              ambiguity_str = '; '.join(ambiguities)
              print(f'  Grade ambiguities: {ambiguity_str}', file=report_file)

            # How do the sets of receiving courses compare? (We know the sending course sets and the
            # rule priorities are the same.)
            r1_component = pair[0].key.split(':')[2]
            r2_component = pair[1].key.split(':')[2]
            same_comp = 'Same' if r1_component == r2_component else 'Different'
            dest_1 = set([(rule.course_id, rule.offer_nbr)
                         for rule in rules_info[0]['dest_courses']])
            dest_2 = set([(rule.course_id, rule.offer_nbr)
                         for rule in rules_info[1]['dest_courses']])
            same_dest = 'same' if dest_1 == dest_2 else 'different'
            print(f'  {same_comp} component subject areas and {same_dest} receiving courses',
                  file=report_file)

            # Are receiving courses BKCR and/or MSG?
            all_blanket_1 = True
            all_message_1 = True
            any_blanket_1 = False
            any_message_1 = False
            for course in rules_info[0]['dest_courses']:
              if course.is_mesg:
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
            for course in rules_info[1]['dest_courses']:
              if course.is_mesg:
                any_message_2 = True
              else:
                all_message_2 = False
              if course.is_bkcr:
                any_blanket_2 = True
              else:
                all_blanket_2 = False

            # Six possibilities:
            #   all all
            #   all any
            #   all none
            #   any any
            #   any none
            #   none none
            if all_blanket_1 and all_blanket_2:
              print('  Both rules are all BKCR', file=report_file)
            elif all_blanket_1 and any_blanket_2 or any_blanket_1 and all_blanket_2:
              print('  One rule is all BKCR; other rule is partly BKCR', file=report_file)
            elif all_blanket_1 and not any_blanket_2 or not any_blanket_1 and all_blanket_2:
              print('  One rule is all BKCR; other rule is not BKCR', file=report_file)
            elif any_blanket_1 and any_blanket_2:
              print('  Both rules are partly BKCR', file=report_file)
            elif any_blanket_1 and not any_blanket_2 or not any_blanket_1 and any_blanket_2:
              print('  One rule is partly BKCR; the other rule is not BKCR', file=report_file)
            else:
              print('  Neither rule is BKCR', file=report_file)

            if all_message_1 and all_message_2:
              print('  Both rules are all MESG', file=report_file)
            elif all_message_1 and any_message_2 or any_message_1 and all_message_2:
              print('  One rule is all MESG; other rule is partly MESG', file=report_file)
            elif all_message_1 and not any_message_2 or not any_message_1 and all_message_2:
              print('  One rule is all MESG; other rule is not MESG', file=report_file)
            elif any_message_1 and any_message_2:
              print('  Both rules are partly MESG', file=report_file)
            elif any_message_1 and not any_message_2 or not any_message_1 and any_message_2:
              print('  One rule is partly MESG; the other rule is not MESG', file=report_file)
            else:
              print('  Neither rule is MESG', file=report_file)
