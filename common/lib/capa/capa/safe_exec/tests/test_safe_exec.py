"""Test safe_exec.py"""

import os.path
import random
import textwrap
import unittest

from capa.safe_exec import safe_exec
from codejail.safe_exec import SafeExecException


class TestSafeExec(unittest.TestCase):
    def test_set_values(self):
        g = {}
        safe_exec("a = 17", g)
        self.assertEqual(g['a'], 17)

    def test_division(self):
        g = {}
        # Future division: 1/2 is 0.5.
        safe_exec("a = 1/2", g)
        self.assertEqual(g['a'], 0.5)

    def test_assumed_imports(self):
        g = {}
        # Math is always available.
        safe_exec("a = int(math.pi)", g)
        self.assertEqual(g['a'], 3)

    def test_random_seeding(self):
        g = {}
        r = random.Random(17)
        rnums = [r.randint(0, 999) for _ in xrange(100)]

        # Without a seed, the results are unpredictable
        safe_exec("rnums = [random.randint(0, 999) for _ in xrange(100)]", g)
        self.assertNotEqual(g['rnums'], rnums)

        # With a seed, the results are predictable
        safe_exec("rnums = [random.randint(0, 999) for _ in xrange(100)]", g, random_seed=17)
        self.assertEqual(g['rnums'], rnums)

    def test_random_is_still_importable(self):
        g = {}
        r = random.Random(17)
        rnums = [r.randint(0, 999) for _ in xrange(100)]

        # With a seed, the results are predictable even from the random module
        safe_exec(
            "import random\n"
            "rnums = [random.randint(0, 999) for _ in xrange(100)]\n",
            g, random_seed=17)
        self.assertEqual(g['rnums'], rnums)

    def test_python_lib(self):
        pylib = os.path.dirname(__file__) + "/test_files/pylib"
        g = {}
        safe_exec(
            "import constant; a = constant.THE_CONST",
            g, python_path=[pylib]
        )

    def test_raising_exceptions(self):
        g = {}
        with self.assertRaises(SafeExecException) as cm:
            safe_exec("1/0", g)
        self.assertIn("ZeroDivisionError", cm.exception.message)


class DictCache(object):
    """A cache implementation over a simple dict, for testing."""

    def __init__(self, d):
        self.cache = d

    def get(self, key):
        # Actual cache implementations have limits on key length
        assert len(key) <= 250
        return self.cache.get(key)

    def set(self, key, value):
        # Actual cache implementations have limits on key length
        assert len(key) <= 250
        self.cache[key] = value


class TestSafeExecCaching(unittest.TestCase):
    """Test that caching works on safe_exec."""

    def test_cache_miss_then_hit(self):
        g = {}
        cache = {}

        # Cache miss
        safe_exec("a = int(math.pi)", g, cache=DictCache(cache))
        self.assertEqual(g['a'], 3)
        # A result has been cached
        self.assertEqual(cache.values()[0], (None, {'a': 3}))

        # Fiddle with the cache, then try it again.
        cache[cache.keys()[0]] = (None, {'a': 17})

        g = {}
        safe_exec("a = int(math.pi)", g, cache=DictCache(cache))
        self.assertEqual(g['a'], 17)

    def test_cache_large_code_chunk(self):
        # Caching used to die on memcache with more than 250 bytes of code.
        # Check that it doesn't any more.
        code = "a = 0\n" + ("a += 1\n" * 12345)

        g = {}
        cache = {}
        safe_exec(code, g, cache=DictCache(cache))
        self.assertEqual(g['a'], 12345)

    def test_cache_exceptions(self):
        # Used to be that running code that raised an exception didn't cache
        # the result.  Check that now it does.
        code = "1/0"
        g = {}
        cache = {}
        with self.assertRaises(SafeExecException):
            safe_exec(code, g, cache=DictCache(cache))

        # The exception should be in the cache now.
        self.assertEqual(len(cache), 1)
        cache_exc_msg, cache_globals = cache.values()[0]
        self.assertIn("ZeroDivisionError", cache_exc_msg)

        # Change the value stored in the cache, the result should change.
        cache[cache.keys()[0]] = ("Hey there!", {})

        with self.assertRaises(SafeExecException):
            safe_exec(code, g, cache=DictCache(cache))

        self.assertEqual(len(cache), 1)
        cache_exc_msg, cache_globals = cache.values()[0]
        self.assertEqual("Hey there!", cache_exc_msg)

        # Change it again, now no exception!
        cache[cache.keys()[0]] = (None, {'a': 17})
        safe_exec(code, g, cache=DictCache(cache))
        self.assertEqual(g['a'], 17)


class TestRealProblems(unittest.TestCase):
    def test_802x(self):
        code = textwrap.dedent("""\
            import math
            import random
            import numpy
            e=1.602e-19 #C
            me=9.1e-31  #kg
            mp=1.672e-27 #kg
            eps0=8.854e-12 #SI units
            mu0=4e-7*math.pi #SI units

            Rd1=random.randrange(1,30,1)
            Rd2=random.randrange(30,50,1)
            Rd3=random.randrange(50,70,1)
            Rd4=random.randrange(70,100,1)
            Rd5=random.randrange(100,120,1)

            Vd1=random.randrange(1,20,1)
            Vd2=random.randrange(20,40,1)
            Vd3=random.randrange(40,60,1)

            #R=[0,10,30,50,70,100] #Ohm
            #V=[0,12,24,36] # Volt

            R=[0,Rd1,Rd2,Rd3,Rd4,Rd5] #Ohms
            V=[0,Vd1,Vd2,Vd3] #Volts
            #here the currents IL and IR are defined as in figure ps3_p3_fig2
            a=numpy.array([  [  R[1]+R[4]+R[5],R[4] ],[R[4], R[2]+R[3]+R[4] ] ])
            b=numpy.array([V[1]-V[2],-V[3]-V[2]])
            x=numpy.linalg.solve(a,b)
            IL='%.2e' % x[0]
            IR='%.2e' % x[1]
            ILR='%.2e' % (x[0]+x[1])
            def sign(x):
                return abs(x)/x

            RW="Rightwards"
            LW="Leftwards"
            UW="Upwards"
            DW="Downwards"
            I1='%.2e' % abs(x[0])
            I1d=LW if sign(x[0])==1 else RW
            I1not=LW if I1d==RW else RW
            I2='%.2e' % abs(x[1])
            I2d=RW if sign(x[1])==1 else LW
            I2not=LW if I2d==RW else RW
            I3='%.2e' % abs(x[1])
            I3d=DW if sign(x[1])==1 else UW
            I3not=DW if I3d==UW else UW
            I4='%.2e' % abs(x[0]+x[1])
            I4d=UW if sign(x[1]+x[0])==1 else DW
            I4not=DW if I4d==UW else UW
            I5='%.2e' % abs(x[0])
            I5d=RW if sign(x[0])==1 else LW
            I5not=LW if I5d==RW else RW
            VAP=-x[0]*R[1]-(x[0]+x[1])*R[4]
            VPN=-V[2]
            VGD=+V[1]-x[0]*R[1]+V[3]+x[1]*R[2]
            aVAP='%.2e' % VAP
            aVPN='%.2e' % VPN
            aVGD='%.2e' % VGD
            """)
        g = {}
        safe_exec(code, g)
        self.assertIn("aVAP", g)