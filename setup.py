#!/usr/bin/env python
# Copyright (C) 2011 Smarkets Limited <support@smarkets.com>
#
# This module is released under the MIT License:
# http://www.opensource.org/licenses/mit-license.php
import glob
import io
import os
import shutil
import subprocess
import sys
from distutils.command import build, clean
from distutils.spawn import find_executable
from itertools import chain
from os.path import abspath, dirname, join

from setuptools import setup


PROJECT_ROOT = abspath(dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)


def check_call(*args, **kwargs):
    print('Calling %s, %s' % (args, kwargs,))
    subprocess.check_call(*args, **kwargs)


ETO_PIQI_URL = 'https://raw.github.com/smarkets/eto_common/v1.2.3/eto.piqi'
SETO_PIQI_URL = 'https://raw.github.com/smarkets/smk_api_common/v6.3.0/seto.piqi'


def _safe_glob(pathname):
    "Do a safe version of glob which copes with win32"
    is_win32 = sys.platform == 'win32'
    for source in glob.glob(pathname):
        yield source.replace('/', '\\') if is_win32 else source


protobuf_modules = ['eto', 'seto']


def protobuf_module_file(name):
    return join(PROJECT_ROOT, 'smarkets', 'streaming_api', '%s.py' % (name,))


class SmarketsProtocolBuild(build.build):

    "Class to build the protobuf output"

    description = "build the protocol buffer output with protobuf-compiler"

    def download(self, url):
        check_call((self.find('wget'), url))

    def find(self, name):
        result = find_executable(name)
        if result is None:
            raise Exception("*** Cannot find %s; make sure it's installed" % (name,))
        return result

    def run(self):
        "Get the .piqi definitions and run the 'protoc' compiler command"

        eto_piqi = join(PROJECT_ROOT, 'eto.piqi')
        if not os.path.exists(eto_piqi):
            self.download(ETO_PIQI_URL)

        seto_piqi = join(PROJECT_ROOT, 'seto.piqi')
        if not os.path.exists(seto_piqi):
            self.download(SETO_PIQI_URL)

        eto_proto = join(PROJECT_ROOT, 'smarkets.streaming_api.eto.proto')
        if not os.path.exists(eto_proto):
            check_call((self.find('piqi'), 'to-proto', eto_piqi, '-o', eto_proto))

        seto_proto = join(PROJECT_ROOT, 'smarkets.streaming_api.seto.proto')
        if not os.path.exists(seto_proto):
            check_call((self.find('piqi'), 'to-proto', seto_piqi, '-o', seto_proto))
            self.replace_file(seto_proto,
                              lambda line: line.replace(
                                  'import "eto.piqi.proto"',
                                  'import "smarkets.streaming_api.eto.proto"'))

        for pkg in protobuf_modules:
            dst_pkg_file = protobuf_module_file(pkg)
            tmp_pkg_file = dst_pkg_file.replace('.py', '_pb2.py')

            if not os.path.exists(dst_pkg_file):
                check_call((self.find('protoc'),
                            '--python_out=.', 'smarkets.streaming_api.%s.proto' % (pkg,)))

                shutil.move(tmp_pkg_file, dst_pkg_file)
                self.replace_file(dst_pkg_file, lambda line: line.replace('_pb2', ''))

        build.build.run(self)

    @staticmethod
    def replace_file(filename, line_map):
        "Map line_map for each line in filename"
        with open(filename, "r") as sources:
            lines = sources.readlines()
        with open(filename, "w") as sources:
            for line in lines:
                sources.write(line_map(line))


class SmarketsProtocolClean(clean.clean):

    """Class to clean up the built protobuf files."""

    description = "clean up files generated by protobuf-compiler"

    def run(self):
        """Do the clean up"""
        for src_dir in [
            join('build', 'pb'),
        ]:
            src_dir = join(PROJECT_ROOT, src_dir)
            if os.path.exists(src_dir):
                shutil.rmtree(src_dir)
        for filename in chain(
                _safe_glob('*.proto'),
                _safe_glob('*.piqi'),
                (join(PROJECT_ROOT, 'smarkets', 'streaming_api', '%s.py' % key)
                 for key in ('eto', 'seto'))):
            if os.path.exists(filename):
                os.unlink(filename)

        # Call the parent class clean command
        clean.clean.run(self)


readme_path = join(PROJECT_ROOT, 'README.rst')

with io.open(readme_path, encoding='utf-8') as f:
    long_description = f.read()


# this is not ideal but at at least we're not repeating ourselved when updating package version

with open(join(PROJECT_ROOT, 'smarkets', '__init__.py')) as f:
    version_line = [line for line in f if line.startswith('__version__')][0]

__version__ = version_line.split('=')[1].strip().strip("'").strip('"')

sdict = {
    'name': 'smk_python_sdk',
    'version': __version__,
    'description': 'Smarkets Python SDK - API clients and utility library',
    'long_description': long_description,
    'url': 'https://github.com/smarkets/smk_python_sdk',
    'download_url': 'https://github.com/smarkets/smk_python_sdk/downloads/smk_python_sdk-%s.tar.gz' % (
        __version__,),
    'author': 'Smarkets Limited',
    'author_email': 'support@smarkets.com',
    'maintainer': 'Smarkets Limited',
    'maintainer_email': 'support@smarkets.com',
    'keywords': ['Smarkets', 'betting exchange'],
    'license': 'MIT',
    'packages': ['smarkets', 'smarkets.streaming_api', 'smarkets.tests'],
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python'],
    'install_requires': [
        'decorator',
        'iso8601',
        'protobuf==3.0.0b2',
        'six',
    ],
    'zip_safe': False,
    'cmdclass': {
        'build': SmarketsProtocolBuild,
        'clean': SmarketsProtocolClean,
    },
}


def creating_a_distribution():
    command_line = ' '.join(sys.argv)
    return 'sdist' in command_line or 'bdist' in command_line


def make_sure_the_package_is_built():
    # It used to be *very* easy to create a sdist/bdist without building
    # the package first and the resulting distribution would be incomplete,
    # this is to prevent that from happening.
    for name in protobuf_modules:
        file_name = protobuf_module_file(name)
        assert os.path.isfile(file_name), '%r not built' % (file_name,)


if __name__ == '__main__':
    if creating_a_distribution():
        make_sure_the_package_is_built()

    setup(**sdict)
