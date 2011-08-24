#!/usr/bin/env python
import glob
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.abspath("."))

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from distutils.spawn import find_executable
from distutils.command import clean, build
from itertools import chain


COMMON_GIT_REPO = 'git://git.corp.smarkets.com/smk_api_common.git'


def _safe_glob(pathname):
    "Do a safe version of glob which copes with win32"
    is_win32 = sys.platform == 'win32'
    for source in glob.glob(pathname):
        yield source.replace('/', '\\') if is_win32 else source


class SmarketsProtocolBuild(build.build):
    "Class to build the protobuf output"

    description = "build the protocol buffer output with protobuf-compiler"

    def check_executables(self):
        "Check that various executables are available"
        self.git = find_executable("git")
        if self.git is None:
            sys.stderr.write("*** Cannot find git; is it installed?\n")
            sys.exit(-1)

        self.protoc = find_executable("protoc")
        if self.protoc is None:
            sys.stderr.write("*** Cannot find protoc; is the protobuf compiler"
                             " installed?\n")
            sys.exit(-1)

        self.piqi = find_executable("piqi")
        if self.piqi is None:
            sys.stderr.write("*** Cannot find piqi; are the piqi build tools"
                             " installed?\n")
            sys.exit(-1)

    def run(self):
        "Get the .piqi definitions and run the 'protoc' compiler command"
        self.check_executables()
        pb_build_dir = os.path.join(
            os.path.dirname(__file__), 'build', 'pb')
        api_dir = os.path.join(pb_build_dir, 'smk_api_common')
        if not os.path.exists(pb_build_dir):
            # Get build
            os.makedirs(pb_build_dir)
            args = (self.git, 'clone', COMMON_GIT_REPO)
            if subprocess.call(args, cwd=pb_build_dir) != 0:
                sys.exit(-1)
            args = ('./rebar', 'get-deps')
            if subprocess.call(args, cwd=api_dir) != 0:
                sys.exit(-1)

        eto_piqi = os.path.join(os.path.dirname(__file__), 'eto.piqi')
        if not os.path.exists(eto_piqi):
            eto_piqi_src = os.path.join(
                api_dir, 'deps', 'eto_common', 'eto.piqi')
            shutil.copy(eto_piqi_src, eto_piqi)

        seto_piqi = os.path.join(os.path.dirname(__file__), 'seto.piqi')
        if not os.path.exists(seto_piqi):
            seto_piqi_src = os.path.join(api_dir, 'seto.piqi')
            shutil.copy(seto_piqi_src, seto_piqi)

        eto_proto = os.path.join(
            os.path.dirname(__file__), 'smarkets.eto.piqi.proto')
        if not os.path.exists(eto_proto):
            args = (self.piqi, 'to-proto', eto_piqi, '-o', eto_proto)
            if subprocess.call(args) != 0:
                sys.exit(-1)

        seto_proto = os.path.join(
            os.path.dirname(__file__), 'smarkets.seto.piqi.proto')
        if not os.path.exists(seto_proto):
            args = (self.piqi, 'to-proto', seto_piqi, '-o', seto_proto)
            if subprocess.call(args) != 0:
                sys.exit(-1)
            self.replace_file(seto_proto, self.fix_import)

        for source in _safe_glob('*.proto'):
            args = (self.protoc, '--python_out=.', source)
            if subprocess.call(args) != 0:
                sys.exit(-1)

        for pkg_dir in ('eto', 'seto'):
            init_file = os.path.join(
                os.path.dirname(__file__), 'smarkets', pkg_dir, '__init__.py')
            open(init_file, 'w').close()

        build.build.run(self)

    @staticmethod
    def replace_file(filename, line_map):
        "Map line_map for each line in filename"
        with open(filename, "r") as sources:
            lines = sources.readlines()
        with open(filename, "w") as sources:
            for line in lines:
                sources.write(line_map(line))

    @staticmethod
    def fix_import(line):
        "Fix the import line in smarkets.seto.piqi.proto"
        return re.sub(
            r'import "eto\.piqi\.proto"',
            'import "smarkets.eto.piqi.proto"',
            line)


class SmarketsProtocolClean(clean.clean):
    """Class to clean up the built protobuf files."""

    description = "clean up files generated by protobuf-compiler"

    def run(self):
        """Do the clean up"""
        for src_dir in [
            os.path.join(os.path.dirname(__file__), 'build', 'pb'),
            os.path.join(os.path.dirname(__file__), 'smarkets', 'eto'),
            os.path.join(os.path.dirname(__file__), 'smarkets', 'seto'),
            ]:
            if os.path.exists(src_dir):
                shutil.rmtree(src_dir)
        for filename in chain(
            _safe_glob('*.proto'),
            _safe_glob('*.piqi')):
            if os.path.exists(filename):
                os.unlink(filename)

        # Call the parent class clean command
        clean.clean.run(self)


readme_path = os.path.join(os.path.dirname(__file__), 'README')
readme_src = os.path.join(os.path.dirname(__file__), 'README.md')

# Generate README from README.md using pandoc
if not os.path.exists(readme_path):
    pandoc = find_executable("pandoc")
    if pandoc is None:
        sys.stderr.write("*** Cannot find pandoc; is it installed?\n")
        sys.exit(-1)
    args = (pandoc, '-s', readme_src, '-w', 'rst', '-o', readme_path)
    if subprocess.call(args) != 0:
        sys.exit(-1)

f = open(readme_path)
long_description = f.read()
f.close()


__version__ = '0.1.0'

sdict = {
    'name' : 'smk',
    'version' : __version__,
    'description' : 'Python client for Smarkets streaming API',
    'long_description' : long_description,
    'url': 'https://github.com/smarkets/smk_python_sdk',
    'download_url' : 'https://github.com/smarkets/smk_python_sdk/downloads/smk-%s.tar.gz' % __version__,
    'author' : 'Smarkets Limited',
    'author_email' : 'support@smarkets.com',
    'maintainer' : 'Smarkets Limited',
    'maintainer_email' : 'support@smarkets.com',
    'keywords' : ['Smarkets', 'betting exchange'],
    'license' : 'MIT',
    'packages' : ['smarkets', 'smarkets.eto', 'smarkets.seto'],
    'test_suite' : 'tests.all_tests',
    'classifiers' : [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python'],
    'cmdclass' : {
        'build': SmarketsProtocolBuild,
        'clean': SmarketsProtocolClean},
    }

setup(**sdict)
