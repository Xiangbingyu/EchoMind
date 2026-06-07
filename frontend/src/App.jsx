import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Messages from './pages/Messages/Messages';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          {/* 默认重定向到消息页 */}
          <Route index element={<Navigate to="/messages" replace />} />
          <Route path="messages" element={<Messages />} />
          {/* 后续可以增加更多页面路由，比如工作台、日历等 */}
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
