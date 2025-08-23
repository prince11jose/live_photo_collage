// App.test.js
import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mocking the fetch function to simulate API responses
global.fetch = jest.fn(() =>
    Promise.resolve({
        json: () => Promise.resolve([{ id: 1, url: 'http://example.com/image1.jpg' }]),
    })
);

describe('App Component', () => {
    beforeEach(() => {
        render(<App />);
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    test('renders the image collage', async () => {
        const images = await screen.findAllByRole('img'); // Assuming you have an <img> element for each image
        expect(images.length).toBeGreaterThan(0);
    });

    test('handles error when fetching images', async () => {
        // Change fetch to reject to simulate an error
        fetch.mockImplementationOnce(() => Promise.reject("API is down"));
        render(<App />);

        const errorMessage = await screen.findByText(/Error fetching images/i);
        expect(errorMessage).toBeInTheDocument();
    });
});
