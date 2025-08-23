import unittest
from flask import json
from app import app  # Ensure this imports your Flask app from the correct file

class FlaskAppTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app.test_client()
        cls.app.testing = True

    def test_get_images(self):
        """Test the API endpoint to fetch current image URLs."""
        response = self.app.get('/api/images')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(json.loads(response.data), list)

    def test_refresh_images(self):
        """Test refreshing images from Google Drive."""
        response = self.app.post('/api/refresh-images', json={"folder_id": "1XnWtpAjglmjA-99zs-ao___16wf7MbKZ"})
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('status', response_data)
        self.assertIn('new_urls', response_data)

if __name__ == '__main__':
    unittest.main()
