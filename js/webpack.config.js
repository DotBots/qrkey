const path = require('path');
const nodeExternals = require('webpack-node-externals');

const isDevelopment = process.env.NODE_ENV !== 'production';

module.exports = {
  entry: './src/index.js',
  mode: isDevelopment ? 'development' : 'production',

  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
        },
      },
    ],
  },

  resolve: {
    extensions: [".js", ".jsx"],
  },

  output: {
    filename: 'qrkey.js',
    path: path.resolve(__dirname, 'dist'),
  },

  externalsPresets: { 
    node: true
  },

  externals: [
    nodeExternals(),
  ],

  plugins: [],
};
