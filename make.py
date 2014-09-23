#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import requests
import sys
import os.path
import json
import shelve
import jinja2
import hashlib
from pprint import pprint

LOCAL_HOST = "http://162.209.109.31:8093/"
BASE_PATH = os.path.abspath(os.path.dirname(__file__))

CACHE_VERSION = 0
CACHE = shelve.open("symbolab_cache")
if CACHE.get("VERSION", 0) < CACHE_VERSION:
    CACHE.clear()

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


def make_exercise(exercise_json):
    problems = []
    exercise = json.load(open(src))
    problems = exercise['problems']
    for problem in problems:
        problem['query'] = query = " ".join([problem['instruction'], problem['latex']])
        problem['exid'] = exid = "SYMB_" + hashlib.md5(query).hexdigest().upper()[:7]
        solution = get_solution(query)

        for k in "computesTo debugInfo".split():
            solution.pop(k, None)
        problem['solution'] = solution.pop('solutions')[0]
        problem.setdefault('title', exercise['default_problem_title'])
        problem.setdefault('latex_buttons', exercise['latex_buttons'])

    name = os.path.splitext(os.path.split(src)[-1])[0]
    fname = "./exercises/%s.html" % name

    from jinja2 import Environment, FileSystemLoader
    env = Environment(trim_blocks=True, lstrip_blocks=True, loader=FileSystemLoader("./"))
    env.filters.update(latex=latex, direction=direction)

    template_name = exercise.get("template", "template.html")
    template = env.get_template(template_name)
    html = template.render(exercise=exercise)
    if obfuscate:
        html = "".join(html.splitlines())

    with open(fname, "w") as f:
        print("Writing %s" % fname)
        print(html.encode("utf8"), file=f)

    for problem in problems:
        print('%(host)s%(url)s?problem=%(exid)s\n\t%(query)s\n' % dict(problem, host=LOCAL_HOST, url=fname))

    print("- Done (%s problems)" % len(problems))


if __name__ == '__main__':
    errors = 0
    for src in sys.argv[1:]:
        try:
            print("\n\n")
            print(("=[ %s ]=" % src).center(80, "-"))
            make_exercise(src)
        except Exception, e:
            sys.excepthook(*sys.exc_info())
            errors += 1
    sys.exit(errors)
