#!/usr/bin/env python
#
# Public Domain 2014-2015 MongoDB, Inc.
# Public Domain 2008-2014 WiredTiger, Inc.
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# test_encrypt04.py
#   Test mismatches error conditions with encryption.
#

import os, run, random
import wiredtiger, wttest
from wtscenario import multiply_scenarios, number_scenarios
from suite_subprocess import suite_subprocess

# Test basic encryption
class test_encrypt04(wttest.WiredTigerTestCase, suite_subprocess):

    uri='table:test_encrypt04'

    encrypt_scen_1 = [
        ('none', dict( name1='none', keyid1='', secretkey1='')),
        ('rotn11', dict( name1='rotn', keyid1='11', secretkey1='')),
        ('rotn17', dict( name1='rotn', keyid1='17', secretkey1='')),
        ('rotn11abc', dict( name1='rotn', keyid1='11', secretkey1='ABC')),
        ('rotn11xyz', dict( name1='rotn', keyid1='11', secretkey1='XYZ'))
    ]
    encrypt_scen_2 = [
        ('none', dict( name2='none', keyid2='', secretkey2='')),
        ('rotn11', dict( name2='rotn', keyid2='11', secretkey2='')),
        ('rotn17', dict( name2='rotn', keyid2='17', secretkey2='')),
        ('rotn11abc', dict( name2='rotn', keyid2='11', secretkey2='ABC')),
        ('rotn11xyz', dict( name2='rotn', keyid2='11', secretkey2='XYZ'))
    ]
    scenarios = number_scenarios(multiply_scenarios \
                                 ('.', encrypt_scen_1, encrypt_scen_2))
    nrecords = 5000
    bigvalue = "abcdefghij" * 1001    # len(bigvalue) = 10010

    def __init__(self, *args, **kwargs):
        wttest.WiredTigerTestCase.__init__(self, *args, **kwargs)
        self.part = 1

    # Override WiredTigerTestCase, we have extensions.
    def setUpConnectionOpen(self, dir):
        if self.part == 1:
            self.name = self.name1
            self.keyid = self.keyid1
            self.secretkey = self.secretkey1
        else:
            self.name = self.name2
            self.keyid = self.keyid2
            self.secretkey = self.secretkey2

        encarg = 'encryption=(name={0},keyid={1},secretkey={2}),'.format(
            self.name, self.keyid, self.secretkey)
        extarg = self.extensionArg([('encryptors', self.name),
            ('encryptors', self.name)])
        self.pr('encarg = ' + encarg + ' extarg = ' + extarg)
        conn = wiredtiger.wiredtiger_open(dir,
            'create,error_prefix="{0}: ",{1}{2}'.format(
                self.shortid(), encarg, extarg))
        self.pr(`conn`)
        return conn

    # Return the wiredtiger_open extension argument for a shared library.
    def extensionArg(self, exts):
        extfiles = []
        for ext in exts:
            (dirname, name) = ext
            if name != None and name != 'none':
                testdir = os.path.dirname(__file__)
                extdir = os.path.join(run.wt_builddir, 'ext', dirname)
                extfile = os.path.join(
                    extdir, name, '.libs', 'libwiredtiger_' + name + '.so')
                if not os.path.exists(extfile):
                    self.skipTest('extension "' + extfile + '" not built')
                if not extfile in extfiles:
                    extfiles.append(extfile)
        if len(extfiles) == 0:
            return ''
        else:
            return ',extensions=["' + '","'.join(extfiles) + '"]'

    # Create a table with encryption values that are in error.
    def test_encrypt(self):
        params = 'key_format=S,value_format=S'
        if self.name != None:
            params += ',encryption=(name=' + self.name + \
                      ',keyid=' + self.keyid + ')'

        self.session.create(self.uri, params)
        cursor = self.session.open_cursor(self.uri, None)
        r = random.Random()
        r.seed(0)
        for idx in xrange(1,self.nrecords):
            start = r.randint(0,9)
            key = self.bigvalue[start:r.randint(0,100)] + str(idx)
            val = self.bigvalue[start:r.randint(0,10000)] + str(idx)
            cursor.set_key(key)
            cursor.set_value(val)
            cursor.insert()
        cursor.close()

        # Now intentially expose the test to mismatched configuration
        self.part = 2
        self.name = self.name2
        self.keyid = self.keyid2
        self.secretkey = self.secretkey

        is_same = (self.name1 == self.name2 and
                   self.keyid1 == self.keyid2 and
                   self.secretkey1 == self.secretkey2)

        # We expect an error if we specified different
        # encryption from one open to the next.  The exception
        # is when we started out with no encryption,
        # we can still enable encryption and read existing files.
        expect_error = not is_same and self.name1 != 'none'

        if expect_error:
            completed = False
            with self.expectedStderrPattern(''):   # effectively ignore stderr
                try:
                    self.reopen_conn()
                    completed = True
                except:
                    pass
                self.assertEqual(False, completed)
        else:
            # Force the cache to disk, so we read
            # compressed/encrypted pages from disk.
            self.reopen_conn()
            cursor = self.session.open_cursor(self.uri, None)
            r.seed(0)
            for idx in xrange(1,self.nrecords):
                start = r.randint(0,9)
                key = self.bigvalue[start:r.randint(0,100)] + str(idx)
                val = self.bigvalue[start:r.randint(0,10000)] + str(idx)
                cursor.set_key(key)
                self.assertEqual(cursor.search(), 0)
                self.assertEquals(cursor.get_value(), val)
            cursor.close()
        

if __name__ == '__main__':
    wttest.run()
