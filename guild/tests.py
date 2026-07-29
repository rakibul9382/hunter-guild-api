from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model  # This handles custom user models!
from .models import HunterProfile
from django.core.cache import cache
from unittest.mock import patch
from django.urls import reverse

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


class ProfileAPITests(APITestCase):

    def test_profile_not_found(self):
        url = '/api/profile/me/'
        test_user = User.objects.create(username='test_hunter', password='supersecretpassword')
        self.client.force_authenticate(user=test_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], "You do not have a Hunter profile set up."
        )

    def test_profile_success(self):
        url = '/api/profile/me/'
        test_user = User.objects.create(username='test_hunter', password='supersecretpassword')
        HunterProfile.objects.create(user=test_user)
        self.client.force_authenticate(user=test_user)
        response = self.client.get(url)
        self.assertTrue(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile', response.data)

    def test_profile_unauthenticated(self):
        url = '/api/profile/me/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("guild.api_views.send_mail")
    def test_request_profile_edit_otp_success(self, mock_send_mail):
        test_user = User.objects.create_user(username='test_hunter', password='supersecretpassword', email="jon@gmail.com")
        HunterProfile.objects.create(user=test_user)
        self.client.force_authenticate(user=test_user)
        response = self.client.post(reverse('request-edit-otp'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "OTP sent to your email successfully."
        )
        otp = cache.get(f'otp_{test_user.id}')
        self.assertIsNotNone(otp)
        self.assertTrue(otp.isdigit())
        mock_send_mail.assert_called_once()

    @patch("guild.api_views.send_mail")
    def test_request_profile_edit_otp_without_profile(self, mock_send_mail):
        test_user = User.objects.create_user(username='test_hunter', password='supersecretpassword', email="jon@gmail.com")
        self.client.force_authenticate(user=test_user)
        response = self.client.post(reverse('request-edit-otp'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "You do not have a Hunter profile set up."
        )
        otp = cache.get(f"otp_{test_user.id}")
        self.assertIsNone(otp)

        mock_send_mail.assert_not_called()

    @patch("guild.api_views.send_mail")
    def test_request_profile_edit_otp_unauthorized(self, mock_send_mail):
        response = self.client.post(reverse('request-edit-otp'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        mock_send_mail.assert_not_called()


class EditProfileTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="hunter",
            email="hunter@gmail.com",
            password="test12345"
        )
        self.profile = HunterProfile.objects.create(
            user=self.user,
            location="Chittagong",
            availability_status="AV"
        )
        self.url =reverse('profile-edit')

    def test_edit_profile_success(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "location": "Dhaka",
            "availability_status": "B"
        }
        response = self.client.patch(self.url,payload,format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.profile.refresh_from_db()

        self.assertEqual(self.profile.location, "Dhaka")
        self.assertEqual(self.profile.availability_status, "B")

    def test_profile_not_found(self):
        user = User.objects.create_user(
            username="john",
            email="john@gmail.com",
            password="123456"
        )

        self.client.force_authenticate(user=user)

        response = self.client.patch(
            self.url,
            {"location": "Dhaka"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data["message"],
            "Profile not found."
        )

    def test_update_email_without_otp(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "email": "new@gmail.com"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.user.refresh_from_db()

        self.assertEqual(self.user.email, "hunter@gmail.com")

    def test_update_phone_without_otp(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "phone_number": "+8801711111111"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_email_invalid_otp(self):
        cache.set(f"otp_{self.user.id}", '123456')
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.url,
            {
                "email": "new@gmail.com",
                "otp": "654321"
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_email_expired_otp(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "email": "new@gmail.com",
                "otp": "123456"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_email_success(self):
        cache.set(f"otp_{self.user.id}", "123456")

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "email": "new@gmail.com",
                "otp": "123456"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()

        self.assertEqual(self.user.email, "new@gmail.com")

    def test_update_phone_success(self):
        cache.set(f"otp_{self.user.id}", "123456")

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "phone_number": "+8801712345678",
                "otp": "123456"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()

        self.assertEqual(
            str(self.user.phone_number),
            "+8801712345678"
        )

    def test_update_multiple_fields(self):
        cache.set(f"otp_{self.user.id}", "123456")

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "location": "Dhaka",
                "availability_status": "B",
                "email": "new@gmail.com",
                "otp": "123456"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.profile.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.profile.location, "Dhaka")
        self.assertEqual(self.profile.availability_status, "B")
        self.assertEqual(self.user.email, "new@gmail.com")

    def test_unauthorized(self):
        response = self.client.patch(
            self.url,
            {
                "location": "Dhaka"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
