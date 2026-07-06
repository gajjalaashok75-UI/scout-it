import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import NotFound from './pages/NotFound'
import DocsHome from './pages/docs/DocsHome'
import Installation from './pages/docs/Installation'
import Quickstart from './pages/docs/Quickstart'
import WebSearch from './pages/docs/WebSearch'
import ImageVideo from './pages/docs/ImageVideo'
import FetchUrl from './pages/docs/FetchUrl'
import MultiEngine from './pages/docs/MultiEngine'
import GitHub from './pages/docs/GitHub'
import Social from './pages/docs/Social'
import CliReference from './pages/docs/CliReference'
import Configuration from './pages/docs/Configuration'
import Output from './pages/docs/Output'
import Api from './pages/docs/Api'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="/docs/" element={<DocsHome />} />
        <Route path="/docs/installation/" element={<Installation />} />
        <Route path="/docs/quickstart/" element={<Quickstart />} />
        <Route path="/docs/web-search/" element={<WebSearch />} />
        <Route path="/docs/image-video/" element={<ImageVideo />} />
        <Route path="/docs/fetch-url/" element={<FetchUrl />} />
        <Route path="/docs/multi-engine/" element={<MultiEngine />} />
        <Route path="/docs/github/" element={<GitHub />} />
        <Route path="/docs/social/" element={<Social />} />
        <Route path="/docs/cli-reference/" element={<CliReference />} />
        <Route path="/docs/configuration/" element={<Configuration />} />
        <Route path="/docs/output/" element={<Output />} />
        <Route path="/docs/api/" element={<Api />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
