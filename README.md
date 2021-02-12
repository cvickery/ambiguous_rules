# Investigate Transfer Rule Patterns
This is part of my [“CUNY Transfer App”](https://transfer-app.qc.cuny.edu), which is the prototype
for [CUNY Transfer Explorer](https://explorer.lehman.edu).

There are many ambiguous course-transfer rules where one course appears as a sending course in more
that one transfer rule with the same min/max grade range and transfer priority, making it impossible
to determine which rule should apply. In PeopleSoft, when a transfer evaluator fetches a student
record that includes such courses, one of the rules is applied, and there is no indication that
another rule (or rules) even exist.

## Rule Structure
A course transfer rule can be identified by a 4-tuple: {sending (source) institution; receiving
(destination) institution; component subject area (subject\_area); source equivalency component
(group\_number)}. We use a _rule\_key_ to represent these tuples as colon (or hyphen) separated
strings. Each rule_key uniquely identifies one transfer rule. An example of a rule key is:

**QCC01:QNS01:CSCI:123**
  - The sending college is Queensborough Community College
  - The receiving college is Queens College
  - The subject\_area is CSCI
  - The group\_number is 123

The _subject\_area_ is an arbitrary string that normally relates to a discipline (computer
  science in this case).

The _group\_number_ is an identifier for the particular courses and conditions where the rule
applies.

Although the most common type of transfer rule (99.5% of the 1.3M rules) tells how one course at a
sending college transfers to one course at a receiving college, in fact the PeopleSoft structure
allows for sets of sending courses to transfer as sets of receiving courses. The sizes of the
sending and receiving sets can be one:one, one:many, many:one, or many:many.

For each course in a sending set, there is a specified range of grades to specify whether the course
is covered by the rule or not. For each course in a receiving set, there is an associated number of
credits.

A one-to-one rule:
**HOS01:LEH01:ANTH:1**
If a student passes ANTH 101 at Hostos (3 credits), it will transfer to Lehman as ANT 211 (also 3
credits).

A one-to-many rule:
**HOS01:LEH01:ACC:3**
If a student passes ACC 110 at Hostos (4 credits), it will transfer to Lehman as ACC 171 (3 credits)
plus ACC 1000 (1 blanket credit in Accounting).

A many-to-many rule:
**QCC01:QNS01:PH:36**
If a student passes PH 411, PH 412, and PH 413 at Queensboro with grades of D or better, they will
transfer to Queens as PHYS 1451, 1454, 1461, and 1464. There are additional rules to cover the three
sending courses when not all three were completed or did not all have the required minimum grade.

### Notes
  - CUNY policy dictates that all credits completed at one college will “count” when a student
    transfers. That is, the number of credits associated with a receiving course set must always
    match the number of credits the student earned by completing the courses in the sending set
    successfully. This project does not deal with cases where rules might contradict this policy
    because the policy will override any discrepancies in the rules.

  - Each transfer rule has an associated _transfer\_priority_ field that determines which rule is
    applied when two rules would otherwise apply in a particular situation.

  - When a student transfers to a receiving college, the transfer admissions officer uses CUNYfirst
    to fetch the student’s courses. The fetch process shows how courses transfer, and the transfer
    officer can examine the transfer rules involved.

## Ambiguituies:

There are situations where more than one transfer rule could determine how a particular course
transfers. That is, two rules might have the same _transfer\_priority_ and a course appears in
both sending sets with some overlapping range of grade requirements. In these cases, when a transfer
officer fetches the courses for a student who completed a course with a grade within the overlapping
range, CUNYfirst will apply one of the rules, and there will be no indication to the transfer
officer that another rule even exists. How CUNYfirst decides which one of the rules to apply is
unclear.

There are different categories of ambiguity, with different levels of importance. The goal of this
project is to identify ambiguous rules and to categorize them so they can be dealt with (or
ignored!) as appropriate.

  - **Duplicated Rule** If the priorities, sending sets (including grade requirements) and receiving
    sets are the same, the rules are redundant and one can simply be eliminated to “clean things
    up.” Either the _subject\_area_ or the _group\_number_ (or both) would have to be different for
    this ambiguity to occur. The rule with the most-appriate _subject\_area_ should be retained, but
    if the _subject\_areas_ are the same, it doesn't matter which rule is kept.

  - **Equivalent Rule** If two rules are ambiguous, but the receiving sets differ only in which of
    two BKCR (blanket credit) constitute the receiving set, the rule with the less-preferred
    receiving course(s) should be eliminated. For example, at Lehman, there are BKCR courses where a
    sending course hasn’t been evaluated yet, and others for where the sending course has been
    evaluated. The rule leading to the evaluated course should be retained and the other one
    dropped.

  - **Blanket versus Real** If one rule leads to blanket credit and the other leads to a ”real
    course” the rule that leads to blanket credit should be dropped.

  - **Multiple Real** If there is ambiguity about which of two non-BKCR receiving course should be
    used, the receiving department or departments will have to be consulted to determine which
    rule should be retained.

## Results

The program, min-max_overlap.py generates two files:

  - _min-max\_overlap.csv_ Lists all courses that appear in two rules but with overlapping grade
    requirement ranges, along with information about the tranfer rules involved. This represents
    the internal data collected for producing the second output file, which is more useful.

  - _rules\_report.txt_ This is a text file that identifies pairs of ambiguous rules, followed by
    information about the nature of the problems found and information that might be helpful for
    deciding how to resolve the problem.
      - For each sending course included in both rules that have overlapping grade ranges, what is
      the range.
      - How do the sending and receiving course sets compare? Note that different sending sets are
      problematic only if they are the same size. If one set is larger than the other, presumably
      the rule that includes a larger group of sending courses will be used.
      - Are the receiving courses all BKCR, mixed BKCR and not, or not BKCR at all. Likewise for
      receiving courses that have one of the “message” designations (MLA and MNL)
