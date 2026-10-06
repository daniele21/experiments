import {
  Activity,
  BarChart3,
  Boxes,
  FileBarChart2,
  GitCompareArrows,
  Layers3,
  Presentation,
  Settings,
  Share2,
  SlidersHorizontal,
  TrendingUp,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { navigate, usePathname } from '../router';

function Link({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      className={className}
      onClick={(event) => {
        if (
          event.button === 0 &&
          !event.metaKey &&
          !event.ctrlKey &&
          !event.shiftKey
        ) {
          event.preventDefault();
          navigate(href);
        }
      }}
    >
      {children}
    </a>
  );
}

export function AppLink({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return <Link href={href} className={className}>{children}</Link>;
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const navigation = [
    ['/overview', BarChart3, 'Overview'],
    ['/executive/scorecard', Presentation, 'Executive'],
    ['/models', Boxes, 'Models'],
    ['/capabilities/structured-output', Layers3, 'Capabilities'],
    ['/frontier', TrendingUp, 'Frontier'],
    ['/sensitivity', SlidersHorizontal, 'Sensitivity'],
    ['/compare', GitCompareArrows, 'Compare'],
    ['/runs', Activity, 'Runs'],
    ['/share', Share2, 'Share'],
  ] as const;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/overview" className="brand">
          <div className="brand-mark">
            <BarChart3 size={17} />
          </div>
          <span>MCB</span>
        </Link>

        <nav className="nav-stack">
          {navigation.map(([href, Icon, label]) => {
            const active =
              pathname === href ||
              (href === '/executive/scorecard' && pathname.startsWith('/executive')) ||
              (href === '/models' && pathname.startsWith('/models/')) ||
              (href.includes('capabilities') && pathname.startsWith('/capabilities')) ||
              (href === '/runs' && pathname.startsWith('/runs/'));
            return (
              <Link
                key={href}
                href={href}
                className={active ? 'nav-item active' : 'nav-item'}
              >
                <Icon size={17} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-spacer" />

        <div className="sidebar-story">
          <strong>Better models through clearer evidence.</strong>
          <span>Open, reproducible evaluation of model capabilities.</span>
          <div className="story-wave" />
        </div>

        <div className="sidebar-footer">
          <a className="nav-item subtle" href="#methodology">
            <FileBarChart2 size={16} />
            <span>Methodology</span>
          </a>
          <span className="nav-item subtle">
            <Settings size={16} />
            <span>Settings</span>
          </span>
        </div>
      </aside>
      <main className="app-content">{children}</main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header premium">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="header-actions">{actions}</div> : null}
    </header>
  );
}
