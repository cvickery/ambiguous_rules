# Investigate Transfer Rule Patterns
This is part of the [CUNY Transfer Explorer project](https://transfer-app.qc.cuny.edu) and https://explorer.lehman.edu

The goal is to produce a list that shows how courses transfer, but so far, two features have not been accounted for, namely grade requirements impacting how a course transfers, and group rules, where a group of sending courses transfer as a group of receiving courses. Here, we explore options for ways to structure such a list.

In the process, it turns out that there are many rules (10K+) that have ambiguous specifications. That is, cases where one course appears as a sending course in more that one transfer rule with the same min/max grade range and transfer priority, making it impossible to determine which rule should apply. In PeopleSoft, when a transfer evaluator fetches a student record that includes such courses, one of the rules is applied, and there is no indication that another rule (or rules) even exist.
# Project Status
This is an exploritory work, not a product. The repository is here so I can access it from different development systems.
