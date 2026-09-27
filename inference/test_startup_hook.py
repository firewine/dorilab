"""CPU-only fresh-container simulation; never runs the real bootstrap or /start.sh."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path('/workspace/dorilab')
class StartupHookTest(unittest.TestCase):
    def test_fresh_and_repeated_start(self):
        with tempfile.TemporaryDirectory() as d:
            temp=Path(d); project=temp/'project';project.mkdir();(project/'inference').mkdir()
            hook=temp/'pre_start.sh';image_start=temp/'start.sh';seen=temp/'observed'
            for name in ['runpod_post_start.sh','bootstrap_runpod.sh','inference/start_inference.sh']:
                (project/name).write_text('#!/bin/bash\nexit 0\n')
            image_start.write_text('#!/bin/bash\nset -e\ntest -L '+str(hook)+'\ntest "$(readlink '+str(hook)+')" = '+str(project/'runpod_post_start.sh')+'\nbash '+str(hook)+'\necho image_start_reached >> '+str(seen)+'\n')
            image_start.chmod(0o755)
            source=(ROOT/'runpod_start.sh').read_text().replace('/workspace/dorilab',str(project)).replace('/pre_start.sh',str(hook)).replace('/start.sh',str(image_start))
            wrapper=temp/'wrapper.sh';wrapper.write_text(source)
            subprocess.run(['bash',str(wrapper),'--check'],check=True,capture_output=True)
            self.assertFalse(hook.exists());self.assertFalse(seen.exists())
            for _ in range(2):subprocess.run(['bash',str(wrapper)],check=True,capture_output=True)
            self.assertEqual(seen.read_text().splitlines(),['image_start_reached']*2)
            hook.unlink();hook.write_text('# unrelated hook\n')
            result=subprocess.run(['bash',str(wrapper)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(hook.read_text(),'# unrelated hook\n')
            self.assertEqual(len(seen.read_text().splitlines()),2)
if __name__=='__main__':unittest.main(verbosity=2)
