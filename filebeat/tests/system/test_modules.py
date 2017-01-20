from filebeat import BaseTest
from beat.beat import INTEGRATION_TESTS
import os
import unittest
import glob
import subprocess
from elasticsearch import Elasticsearch
import json
import logging


class Test(BaseTest):
    def init(self):
        self.elasticsearch_url = self.get_elasticsearch_url()
        print("Using elasticsearch: {}".format(self.elasticsearch_url))
        self.es = Elasticsearch([self.elasticsearch_url])
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("elasticsearch").setLevel(logging.ERROR)

        self.modules_path = os.path.abspath(self.working_dir +
                                            "/../../../../module")

        self.filebeat = os.path.abspath(self.working_dir +
                                        "/../../../../filebeat.test")

        self.index_name = "test-filebeat-modules"

    @unittest.skipIf(not INTEGRATION_TESTS or
                     os.getenv("TESTING_ENVIRONMENT") == "2x",
                     "integration test not available on 2.x")
    def test_modules(self):
        self.init()
        modules = os.getenv("TESTING_FILEBEAT_MODULES")
        if modules:
            modules = modules.split(",")
        else:
            modules = os.listdir(self.modules_path)

        # generate a minimal configuration
        cfgfile = os.path.join(self.working_dir, "filebeat.yml")
        self.render_config_template(
            template="filebeat_modules.yml.j2",
            output=cfgfile,
            index_name=self.index_name,
            elasticsearch_url=self.elasticsearch_url)

        for module in modules:
            path = os.path.join(self.modules_path, module)
            filesets = [name for name in os.listdir(path) if
                        os.path.isfile(os.path.join(path, name,
                                                    "manifest.yml"))]

            for fileset in filesets:
                test_files = glob.glob(os.path.join(self.modules_path, module,
                                                    fileset, "test", "*.log"))
                for test_file in test_files:
                    self.run_on_file(
                        module=module,
                        fileset=fileset,
                        test_file=test_file,
                        cfgfile=cfgfile)

    def run_on_file(self, module, fileset, test_file, cfgfile):
        print("Testing {}/{} on {}".format(module, fileset, test_file))

        try:
            self.es.indices.delete(index=self.index_name)
        except:
            pass

        cmd = [
            self.filebeat, "-systemTest",
            "-e", "-d", "*", "-once", "-setup",
            "-c", cfgfile,
            "-modules={}".format(module),
            "-M", "{module}.{fileset}.var.paths=[{test_file}]".format(
                module=module, fileset=fileset, test_file=test_file),
            "-M", "*.*.prospector.close_eof=true",
        ]
        output = open(os.path.join(self.working_dir, "output.log"), "ab")
        output.write(" ".join(cmd) + "\n")
        subprocess.Popen(cmd,
                         stdin=None,
                         stdout=output,
                         stderr=subprocess.STDOUT,
                         bufsize=0).wait()

        # Make sure index exists
        self.wait_until(lambda: self.es.indices.exists(self.index_name))

        self.es.indices.refresh(index=self.index_name)
        res = self.es.search(index=self.index_name,
                             body={"query": {"match_all": {}}})
        objects = [o["_source"] for o in res["hits"]["hits"]]
        assert len(objects) > 0
        for obj in objects:
            self.assert_fields_are_documented(obj)
            # assert "error" not in obj  # no parsing errors

        if os.path.exists(test_file + "-expected.json"):
            with open(test_file + "-expected.json", "r") as f:
                expected = json.load(f)
                assert len(expected) == len(objects)
                for ev in expected:
                    found = False
                    for obj in objects:
                        if ev["_source"][module] == obj[module]:
                            found = True
                            break
                    if not found:
                        raise Exception("The following expected object was" +
                                        " not found: {}".format(obj))
