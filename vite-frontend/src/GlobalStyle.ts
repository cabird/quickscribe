// GlobalStyle.ts
import { createGlobalStyle } from 'styled-components';

const GlobalStyle = createGlobalStyle`
  body {
    background: linear-gradient(135deg, #f0f4f8 0%, #d9e4ec 100%);
    min-height: 100vh;
    margin: 0;
    font-family: 'Arial', sans-serif;
  }
`;

export default GlobalStyle;
