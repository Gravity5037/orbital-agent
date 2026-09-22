import unittest, platform, orbitalchat
class TestHostBaseline(unittest.TestCase):
    def test_platform_detection(self):
        self.assertTrue(len(platform.system()) > 0)
    def test_orbitalchat_functions(self):
        self.assertTrue(hasattr(orbitalchat, "get_system_info"))
        self.assertTrue(hasattr(orbitalchat, "execute_local_command"))
    def test_system_info_string(self):
        info = orbitalchat.get_system_info()
        self.assertIn("OS: ", info)
        self.assertIn("Processor: ", info)
    def test_local_command_execution(self):
        res = orbitalchat.execute_local_command("echo orbital_test")
        self.assertIn("orbital_test", res)
if __name__ == "__main__": unittest.main()