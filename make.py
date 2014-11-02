#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import requests
import sys
from os.path import basename, splitext, join, exists
import os.path
import argparse
import json
import shelve
import jinja2
import hashlib
import itertools
import random
from pprint import pprint

LOCAL_HOST = "http://162.209.109.31:8093/"
BASE_PATH = os.path.abspath(os.path.dirname(__file__))

CACHE_VERSION = 2
CACHE = shelve.open("symbolab_cache")
if CACHE.get("VERSION", 0) < CACHE_VERSION:
    CACHE.clear()
    CACHE["VERSION"] = CACHE_VERSION

URL_SYMBOLAB = "http://www.scibug.com/steps"

defaults = dict(flat="true", language="he", userId="khanIL")
obfuscate = False

def get_solution(query):

    params = dict(query=query, **defaults)
    key = repr(tuple(sorted(params.items())))

    try:
        return CACHE[key]
    except KeyError:
        pass

    for i in range(20):
        data = None
        try:
            print("Fetching from %s..." % key)
            ret = requests.get(URL_SYMBOLAB, params=params)
            print("Fetched: %s" % ret.url)
            ret.raise_for_status()
            data = ret.json()
            assert data['solutions']
            data['problem'] = query
            CACHE[key] = data
            return data
        except KeyError:
            raise Exception("No solutions for '%s'" % query)
        except ValueError:
            raise
        except Exception as e:
            if data:
                print(data.request.url)
            print(i, e)
            # import random
            # gevent.sleep(random.randint(1, 30))
            continue
    raise


import re
RE_TEXT_EXTRACT = re.compile(r"(\\mathrm{[^}]+})")
RE_TEXT = re.compile(r"\\mathrm{([^}]+)}")

def latex(code):
    def g():
        for e in RE_TEXT_EXTRACT.split(code):
            if not e:
                continue
            text = RE_TEXT.match(e)
            if not text:
                yield "<code>%s</code>" % e.replace(" ", "\\:")
            else:
                yield "<span>%s</span>" % text.group(1)
    if not code:
        return ""
    return "&nbsp;".join(reversed(list(g())))


def direction(code):
    return "rtl" if "mathrm" in code else "ltr"



RE_VAR = re.compile(r"\[([\w^*/+-.\(\)]*)\]")
def make_problem(latex, vardict):
    def sub(expr):
        expr, = expr.groups()
        ret = str(eval(expr.replace("^", "**"), {}, vardict))
        # print(expr, "-->", ret)
        return ret
    ret = RE_VAR.sub(sub, latex)
    print("\t %s \t--> %s" % (vardict, ret))
    return ret


def expand_problems(problems):
    for problem in problems:
        variables = problem.pop("vars", None)
        if not variables:
            yield dict(problem)
            continue
        latex = problem.pop('latex')
        print("Expanding: ", latex)
        for k, v in variables.items():
            if len(v)==2:
                variables[k] = xrange(v[0], v[1]+1)
        keys = variables.keys()
        samples = problem.pop("samples", False)
        permutations = itertools.product(*variables.itervalues())
        if samples:
            permutations = random.sample(list(permutations), samples)
        for values in permutations:
            d = dict(zip(map(str, keys), values))
            sub_problem = dict(problem)
            sub_problem['latex'] = make_problem(latex, d)
            yield sub_problem


def make_exercise(src, tgt):
    problems = []
    exercise = json.load(open(src))
    problems = []
    for problem in expand_problems(exercise.pop('problems')):
        problem['query'] = query = " ".join([problem['instruction'], problem['latex']])
        problem['exid'] = exid = "SYMB_" + hashlib.md5(query).hexdigest().upper()[:7]
        solution = get_solution(query)

        for k in "computesTo debugInfo".split():
            solution.pop(k, None)
        problem['solution'] = solution.pop('solutions')[0]
        problem.setdefault('title', exercise['default_problem_title'])
        problem.setdefault('latex_buttons', exercise['latex_buttons'])
        problems.append(problem)
    exercise['problems'] = problems

    from jinja2 import Environment, FileSystemLoader
    env = Environment(trim_blocks=True, lstrip_blocks=True, loader=FileSystemLoader(BASE_PATH))
    env.filters.update(latex=latex, direction=direction)

    template_name = exercise.get("template", "template.html")
    template = env.get_template(template_name)
    html = template.render(exercise=exercise)
    if obfuscate:
        html = "".join(html.splitlines())

    with open(tgt, "w") as f:
        print("Writing %s" % tgt)
        print(html.encode("utf8"), file=f)

    for problem in problems:
        print('%(host)s%(url)s?problem=%(exid)s\n\t%(query)s\n' % dict(problem, host=LOCAL_HOST, url=tgt))

    print("- Done (%s problems)" % len(problems))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="+", help="The exercise json files to make")
    parser.add_argument("--target", default="./exercises/", help="Target path for exercises")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing exercises")
    args = parser.parse_args()

    errors = 0
    for src in args.source:
        tgt = "%s.html" % splitext(basename(src))[0]
        tgt = join(args.target, tgt)
        if exists(tgt) and not args.overwrite:
            print("Skipping existing exercise: %s" % tgt)
            continue

        try:
            print("\n")
            print(("=[ %s ]=" % src).center(80, "-"))
            make_exercise(src, tgt)
            print("\n")
        except Exception as e:
            sys.excepthook(*sys.exc_info())
            errors += 1

    sys.exit(errors)

if __name__ == '__main__':
    main()
