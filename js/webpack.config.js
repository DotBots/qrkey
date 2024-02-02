const path = require('path');
const nodeExternals = require('webpack-node-externals');

module.exports = {
  entry: './src/qrkey.js',
  output: {
    filename: 'qrkey.js',
    path: path.resolve(__dirname, 'dist'),
  },
  mode: "production",

  module: {
    rules: [
      {
        test: /.(js|jsx)$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
          options:{
            presets: ["@babel/preset-env", "@babel/preset-react"],
          }
        },
      },
    ],
  },
  externalsPresets: { 
    node: true
  },
  externals: [
    nodeExternals(),
  ],
  plugins: [],
};
