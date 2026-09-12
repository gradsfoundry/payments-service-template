const express = require('express');

const app = express();

const orders = [
  { id: 1, item: 'Laptop stand', status: 'shipped' },
  { id: 2, item: 'Mechanical keyboard', status: 'processing' },
];

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

app.get('/orders', (req, res) => {
  res.status(200).json(orders);
});

if (require.main === module) {
  const port = process.env.PORT || 3000;
  app.listen(port, () => {
    console.log(`orders-api listening on port ${port}`);
  });
}

module.exports = app;
