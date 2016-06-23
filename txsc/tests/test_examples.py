"""Tests for scripts in the examples/ directory."""
import unittest

from txsc.tests import BaseCompilerTest

class ExampleTest(BaseCompilerTest):
    @classmethod
    def _options(cls):
        namespace = super(ExampleTest, cls)._options()
        namespace.optimization = 2
        return namespace

    def test_function(self):
        """Test examples/function.txscript."""
        expected = '6'
        src = ['func int addA(x) {return x + A;}',
               'let A = 5;',
               'addA(1);']
        self._test(expected, src)

    def test_p2ph_script(self):
        """Test examples/p2ph-script.txscript."""
        expected = 'DUP HASH160 0x14 0x1010101010101010101010101010101010101010 EQUALVERIFY CHECKSIG'
        src = ["assume sig, pubkey;",
               "verify hash160(pubkey) == '1010101010101010101010101010101010101010';",
               "checkSig(sig, pubkey);"]
        self._test(expected, src)

    def test_p2sh_scriptsig(self):
        """Test examples/p2sh-scriptsig.txscript."""
        expected = "0 0x48 0x304502200187af928e9d155c4b1ac9c1c9118153239aba76774f775d7c1f9c3e106ff33c0221008822b0f658edec22274d0b6ae9de10ebf2da06b1bbdaaba4e50eb078f39e3d7801 0x47 0x30440220795f0f4f5941a77ae032ecb9e33753788d7eb5cb0c78d805575d6b00a1d9bfed02203e1f4ad9332d1416ae01e27038e945bc9db59c732728a383a6f1ed2fb99da7a401 0xc9 0x52410491bba2510912a5bd37da1fb5b1673010e43d2c6d812c514e91bfa9f2eb129e1c183329db55bd868e209aac2fbc02cb33d98fe74bf23f0c235d6126b1d8334f864104865c40293a680cb9c020e7b1e106d8c1916d3cef99aa431a56d253e69256dac09ef122b1a986818a7cb624532f062c1d1f8722084861c5c3291ccffef4ec687441048d2455d2403e08708fc1f556002f1b6cd83f992d085097f9974ab08a28838f07896fbab08f39495e15fa6fad6edbfb1e754e35fa1c7844c41f322a1863d4621353ae"
        src = [
            "let pubKeyA = '0491bba2510912a5bd37da1fb5b1673010e43d2c6d812c514e91bfa9f2eb129e1c183329db55bd868e209aac2fbc02cb33d98fe74bf23f0c235d6126b1d8334f86';",
            "let pubKeyB = '04865c40293a680cb9c020e7b1e106d8c1916d3cef99aa431a56d253e69256dac09ef122b1a986818a7cb624532f062c1d1f8722084861c5c3291ccffef4ec6874';",
            "let pubKeyC = '048d2455d2403e08708fc1f556002f1b6cd83f992d085097f9974ab08a28838f07896fbab08f39495e15fa6fad6edbfb1e754e35fa1c7844c41f322a1863d46213';",

            "let sigA = '304502200187af928e9d155c4b1ac9c1c9118153239aba76774f775d7c1f9c3e106ff33c0221008822b0f658edec22274d0b6ae9de10ebf2da06b1bbdaaba4e50eb078f39e3d7801';",
            "let sigB = '30440220795f0f4f5941a77ae032ecb9e33753788d7eb5cb0c78d805575d6b00a1d9bfed02203e1f4ad9332d1416ae01e27038e945bc9db59c732728a383a6f1ed2fb99da7a401';",

            "let redeemScript = raw(checkMultiSig(2, pubKeyA, pubKeyB, pubKeyC, 3));",

            "0;",
            "sigA; sigB;",
            "redeemScript;"
        ]
        self._test(expected, src)

    def test_superscript_example(self):
        """Test examples/superscript-example.txscript."""
        expected = 'SHA256 0x20 0x527ccdd755dcccf03192383624e0a7d0263815ce2ecf1f69cb0423ab7e6f0f3e EQUAL SWAP 0x41 0x04c9ce67ff2df2cd6be5f58345b4e311c5f10aab49d3cf3f73e8dcac1f9cd0de966e924be091e7bc854aef0d0baafa80fe5f2d6af56b1788e1e8ec8d241b41c40d CHECKSIG BOOLOR SWAP 0x41 0x04d4bf4642f56fc7af0d2382e2cac34fa16ed3321633f91d06128f0e5c0d17479778cc1f2cc7e4a0c6f1e72d905532e8e127a031bb9794b3ef9b68b657f51cc691 CHECKSIG BOOLAND'
        src = [
            "assume signatureA, signatureB, secret;"

            "let secretKnown = sha256(secret) == '527ccdd755dcccf03192383624e0a7d0263815ce2ecf1f69cb0423ab7e6f0f3e';"

            "let pubKeyA = '04d4bf4642f56fc7af0d2382e2cac34fa16ed3321633f91d06128f0e5c0d17479778cc1f2cc7e4a0c6f1e72d905532e8e127a031bb9794b3ef9b68b657f51cc691';"
            "let pubKeyB = '04c9ce67ff2df2cd6be5f58345b4e311c5f10aab49d3cf3f73e8dcac1f9cd0de966e924be091e7bc854aef0d0baafa80fe5f2d6af56b1788e1e8ec8d241b41c40d';"

            "let signedByA = checkSig(signatureA, pubKeyA);"
            "let signedByB = checkSig(signatureB, pubKeyB);"

            "verify (secretKnown or signedByB) and signedByA;"
        ]
        self._test(expected, src)

    def test_mark_invalid_example(self):
        """Test examples/mark-invalid.txscript."""
        expected = 'RETURN 0x04 0x74657374'
        src = ["markInvalid();", "push \"test\";", "markInvalid();"]
        self._test(expected, src)

    def test_builtin_functions_example(self):
        """Test examples/builtin-functions.txscript."""
        expected = '5 6 5 1'
        src = ["push min(5, 6);", "push max(5, 6);", "push abs(-5);", "push size('5');"]
        self._test(expected, src)
