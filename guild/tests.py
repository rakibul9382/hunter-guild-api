from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model  # This handles custom user models!

User = get_user_model()


class TaskAPITests(APITestCase):

    def test_get_task_list_authenticated(self):
        """
        Ensure ONLY authenticated users can view the task list.
        """
        # 1. Create a fake test user
        test_user = User.objects.create_user(username='test_hunter', password='supersecretpassword')

        # 2. Log the test client in
        self.client.force_authenticate(user=test_user)

        # 3. Make the request
        url = '/api/tasks/'
        response = self.client.get(url)

        # Now we expect a 200 OK because we are logged in!
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_task_unauthorized(self):
        """
        Ensure unauthenticated users CANNOT create a task (POST request).
        """
        url = '/api/tasks/'
        data = {'title': 'Hunt a Dragon', 'reward': 500}

        response = self.client.post(url, data)

        # We expect a 401 Unauthorized or 403 Forbidden status code
        self.assertTrue(response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])