# vim: tabstop=4 shiftwidth=4 softtabstop=4

import time
from nose.plugins.attrib import attr

from tempest.common.utils.data_utils import arbitrary_string
from tempest.common.utils.data_utils import rand_name
from tempest.tests.object_storage import base


class ContainerSyncTest(base.BaseObjectTest):

    @classmethod
    def setUpClass(cls):
        super(ContainerSyncTest, cls).setUpClass()

        container_sync_timeout = \
                int(cls.config.object_storage.container_sync_timeout)
        cls.container_sync_interval = \
                int(cls.config.object_storage.container_sync_interval)
        cls.attempts = int(container_sync_timeout / \
                            cls.container_sync_interval)

        cls.containers = []
        cls.objects = []

        # Define container and object clients
        cls.clients = {}
        cls.clients[rand_name(name='TestContainerSync')] = \
                    (cls.container_client, cls.object_client)
        cls.clients[rand_name(name='TestContainerSync')] = \
                    (cls.container_client_alt, cls.object_client_alt)

    @classmethod
    def tearDownClass(cls):
        for cont_name, client in cls.clients.items():
            #Get list of all object in the container
            objlist = client[0].list_all_container_objects(cont_name)

            #Attempt to delete every object in the container
            for obj in objlist:
                resp, _ = client[1].delete_object(cont_name, obj['name'])

            #Attempt to delete the container
            resp, _ = client[0].delete_container(cont_name)

    @attr(type='smoke')
    def test_container_sync(self):
        """Container to container synchronization"""

        #Create a containers
        for cont_name, client in self.clients.items():
            resp, body = client[0].create_container(cont_name)
            self.assertTrue(resp['status'] in ('202', '201'),
                    'Error creating the container "%s"' % (cont_name))
            self.containers.append(cont_name)

        #Switch container synchronization on and create objects in a containers
        for cont in (self.containers, self.containers[::-1]):
            cont_client = [self.clients[c][0] for c in cont]
            obj_client = [self.clients[c][1] for c in cont]

            #tell first container to syncronize to a second
            headers = {
                    'X-Container-Sync-Key': 'sync_key',
                    'X-Container-Sync-To': "%s/%s" %\
                        (cont_client[1].base_url, str(cont[1]))
                }
            resp, body = \
                cont_client[0].put(str(cont[0]), body=None, headers=headers)
            self.assertTrue(resp['status'] in ('202', '201'),
                        'Error installing X-Container-Sync-To '
                        'for the container "%s"' % (cont[0]))

            #Create Object in container
            object_name = rand_name(name='TestSyncObject')
            data = object_name[::-1]  # arbitrary_string()
            resp, _ = obj_client[0].create_object(cont[0], object_name, data)
            self.assertEqual(resp['status'], '201',
                    'Error creating the object "%s" in the container "%s"'\
                    % (object_name, cont[0]))
            self.objects.append(object_name)

        #Wait for Container contents list json format will be not empty
        cont_client = [self.clients[c][0] for c in self.containers]
        params = {'format': 'json'}
        while self.attempts > 0:
            # get first container content
            resp, object_list_0 = \
                cont_client[0].\
                list_container_contents(self.containers[0], params=params)
            self.assertEqual(resp['status'], '200',
                    'error listing the destination container`s "%s" contents'\
                            % (self.containers[0]))
            object_list_0 = {obj['name']: obj for obj in object_list_0}
            # get second container content
            resp, object_list_1 = \
                cont_client[1].\
                list_container_contents(self.containers[1], params=params)
            self.assertEqual(resp['status'], '200',
                    'error listing the destination container`s "%s" contents'\
                            % (self.containers[1]))
            object_list_1 = {obj['name']: obj for obj in object_list_1}
            # check that containers is not empty and has equal keys()
            # or wait for next attepmt
            if not object_list_0 or not object_list_1 or \
                    set(object_list_0.keys()) != set(object_list_1.keys()):
                time.sleep(self.container_sync_interval)
                self.attempts -= 1
            else:
                break

        # Check for synchronization
        self.assertEqual(object_list_0, object_list_1,
                'Different object lists in containers.')
