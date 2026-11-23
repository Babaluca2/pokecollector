import { useState, useMemo, useId, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  RefreshCw, LogOut,
  Search, Library, Grid2X2, BarChart3, Settings, ArrowRightLeft, ListOrdered, Info, Layers3,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import { getDashboard, triggerPriceSync, getSyncStatus, getInvestmentTracker, getScanJobs } from '../api/client'
import { useSettings } from '../contexts/SettingsContext'
import { useAuth } from '../contexts/AuthContext'
import toast from 'react-hot-toast'
import { collectionItemTargetUrl } from '../utils/navigation'
import { CardLegend, withCollectionItemState } from '../components/card-system'
import { CollectionCardDisplay } from '../components/CollectionCardImage'
import {
  SCAN_JOBS_QUERY_KEY,
  hasActiveScanJobs,
  scanAttentionCount,
} from '../utils/scanJobs'
import { mapPortfolioChartData, portfolioApiPeriod, PORTFOLIO_PERIODS } from '../utils/portfolioChart'

// Compact number formatter for mobile (1.2k, 3.4M, etc.)
function compactNum(n) {
  if (typeof n === 'string') return n // already formatted (e.g. price)
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 10_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k'
  return n.toLocaleString()
}

// ── Custom chart tooltip ──────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, formatPrice }) {
  if (!active || !payload?.length) return null
  const tooltipLabel = payload[0]?.payload?.tooltipLabel || label
  return (
    <div className="rounded-xl px-3 py-2 text-xs shadow-xl"
      style={{ background: 'var(--color-elevated)', border: '1px solid var(--color-border)' }}>
      <p className="text-text-muted mb-1">{tooltipLabel}</p>
      <p className="font-black" style={{ color: '#f5c842' }}>
        {formatPrice(Number(payload[0].value))}
      </p>
      {payload[0]?.payload?.legacy && (
        <p className="mt-1 text-[10px] text-text-muted">{payload[0].payload.legacyLabel}</p>
      )}
    </div>
  )
}

// ── Card thumbnail ────────────────────────────────────────────────────────────
function CardThumb({ card, onClick }) {
  return (
    <div className="w-[110px] flex-shrink-0">
      <CollectionCardDisplay
        variant="artwork"
        item={{ id: card.collection_item_id, has_scan_photo: card.has_scan_photo }}
        card={card}
        alt={card.name}
        variantEffectSource={card.variant}
        interactive
        onClick={onClick}
        stateIndicatorProps={{ card: withCollectionItemState(card, card), alwaysShowQuantity: true }}
      />
    </div>
  )
}

function ProductValueInfo({ label, detailsLabel, explanation }) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const descriptionId = useId()
  const visible = !dismissed && (hovered || focused)
  useEffect(() => {
    if (!visible) return undefined
    const dismissOnEscape = (event) => {
      if (event.key === 'Escape') setDismissed(true)
    }
    window.addEventListener('keydown', dismissOnEscape)
    return () => window.removeEventListener('keydown', dismissOnEscape)
  }, [visible])

  return (
    <span
      className="relative inline-flex items-center justify-center gap-1.5"
      onMouseEnter={() => {
        setHovered(true)
        setDismissed(false)
      }}
      onMouseLeave={() => {
        setHovered(false)
      }}
      onFocus={() => {
        setFocused(true)
        setDismissed(false)
      }}
      onBlur={() => {
        setFocused(false)
      }}
    >
      {label ? <span className="text-xs text-text-muted">{label}</span> : null}
      <button
        type="button"
        aria-label={label ? `${label}: ${detailsLabel}` : detailsLabel}
        aria-describedby={descriptionId}
        className="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-muted transition-colors hover:text-yellow focus-visible:text-yellow focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-yellow/60"
      >
        <Info size={12} aria-hidden="true" />
      </button>
      <span id={descriptionId} className="sr-only">{explanation}</span>
      {visible && (
        <span
          aria-hidden="true"
          className="absolute left-1/2 top-full z-30 w-[min(16rem,calc(100vw-2rem))] -translate-x-1/2 pt-2"
        >
          <span className="block rounded-lg border border-border bg-bg-surface px-3 py-2 text-left text-[10px] font-normal normal-case leading-relaxed tracking-normal text-text-secondary shadow-xl">
            {explanation}
          </span>
        </span>
      )}
    </span>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function HomeScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { formatPrice, t, pricePrimaryField, settings, updateSettings } = useSettings()
  const { user, logout, multiUser } = useAuth()
  const [chartPeriod, setChartPeriod] = useState('1W')

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', pricePrimaryField],
    queryFn: () => getDashboard({ price_field: pricePrimaryField }).then(r => r.data),
    refetchInterval: 60000,
  })

  const { data: syncStatus } = useQuery({
    queryKey: ['sync-status'],
    queryFn: () => getSyncStatus().then(r => r.data),
    refetchInterval: 15000,
  })

  const { data: scanData } = useQuery({
    queryKey: SCAN_JOBS_QUERY_KEY,
    queryFn: getScanJobs,
    refetchInterval: query => hasActiveScanJobs(query.state.data?.jobs || []) ? 3000 : false,
  })
  const scanJobs = scanData?.jobs || []
  const scanAttention = scanAttentionCount(scanJobs)
  const scansActive = hasActiveScanJobs(scanJobs)

  // Portfolio history for chart — uses analytics/investment-tracker
  const { data: investmentData = [] } = useQuery({
    queryKey: ['investment-tracker', chartPeriod, pricePrimaryField],
    queryFn: () => getInvestmentTracker({ period: portfolioApiPeriod(chartPeriod), price_field: pricePrimaryField }).then(r => r.data),
    refetchInterval: 120000,
  })

  const trainerName = user?.username || 'Trainer'

  const syncMutation = useMutation({
    mutationFn: triggerPriceSync,
    onSuccess: () => {
      toast.success(t('settings.syncStarted'))
      setTimeout(() => queryClient.invalidateQueries(), 3000)
    },
    onError: () => toast.error(t('settings.syncFailed')),
  })

  const isRunning = syncStatus?.is_running || syncStatus?.is_price_sync_running || syncMutation.isPending

  const totalValue = Number(data?.total_value ?? 0)
  const totalCost = Number(data?.total_cost ?? 0)
  const performanceCostBasis = Number(data?.performance_cost_basis ?? totalCost)
  const pnl = Number(data?.pnl ?? 0)
  const pnlPct = performanceCostBasis > 0 ? (pnl / performanceCostBasis) * 100 : 0
  const pnlPositive = pnl >= 0
  const realizedPnl = Number(data?.realized_pnl ?? 0)
  const realizedValue = Number(data?.realized_value ?? 0)
  // Net invested = cards cost + unsold products cost — i.e. money currently deployed
  const netInvested = totalCost
  const portfolioDisplayMode = settings?.portfolio_display_mode === 'capital_invested'
    ? 'capital_invested'
    : 'portfolio_value'
  const showingPortfolioValue = portfolioDisplayMode === 'portfolio_value'
  const headlineValue = showingPortfolioValue ? totalValue : netInvested
  const headlineLabel = showingPortfolioValue ? t('home.portfolioValue') : t('home.capitalInvested')
  const productValueFallbackCount = Number(data?.product_value_fallback_count ?? 0)
  const productsNeedingReviewCount = Number(data?.products_needing_review_count ?? 0)
  const productValueExplanation = [
    productsNeedingReviewCount > 0
      ? `${productsNeedingReviewCount} ${t('home.productsNeedReview')}`
      : '',
    productValueFallbackCount > 0
      ? `${productValueFallbackCount} ${t('home.productValueFallback')}`
      : '',
  ].filter(Boolean).join(' ')

  const setPortfolioDisplayMode = (mode) => {
    if (mode === portfolioDisplayMode) return
    updateSettings({ portfolio_display_mode: mode }).catch(() => {
      toast.error(t('home.displayModeSaveFailed'))
    })
  }

  const recentCards = data?.recent_additions?.slice(0, 12) ?? []
  const topCards = data?.top_cards?.slice(0, 8) ?? []

  const openCollectionItem = (card) => navigate(collectionItemTargetUrl(card))

  // Map chart data — backend already filters and downsamples
  const chartData = useMemo(
    () => mapPortfolioChartData(investmentData, chartPeriod, t('home.legacySnapshot')),
    [investmentData, chartPeriod, t],
  )

  // Determine chart color based on trend
  const chartColor = useMemo(() => {
    if (chartData.length < 2) return '#B79B63'
    const first = chartData[0]?.value ?? 0
    const last = chartData[chartData.length - 1]?.value ?? 0
    return last >= first ? '#B79B63' : '#C8806F'
  }, [chartData])

  // Portal navigation items — defined inside component so t() works
  const PORTAL_ITEMS = [
    { to: '/collection', icon: Library,    label: t('nav.collection') },
    {
      to: '/search',
      icon: Search,
      label: t('nav.cardSearch'),
      badge: scanAttention,
      active: scansActive,
    },
    { to: '/sets',       icon: Grid2X2,    label: t('nav.sets'),        color: '#81c784' },
    { to: '/pokedex',    icon: ListOrdered, label: t('nav.pokedex'),    color: '#ffb74d' },
    { to: '/binders',    icon: Layers3,     label: t('nav.binders'),    color: '#7986cb' },
    { to: '/analytics',  icon: BarChart3,  label: t('nav.analytics'),   color: '#f5c842' },
    { to: '/trades',     icon: ArrowRightLeft, label: t('nav.trades'),   color: '#ff8a65' },
    { to: '/settings',   icon: Settings,   label: t('nav.settings'),    color: '#b0bec5' },
  ]

  const gain = pnlPositive ? '#8DB596' : '#C8806F'
  const stats = [
    [compactNum(data?.total_cards ?? 0), t('home.cardsTotal')],
    [compactNum(data?.owned_sets ?? 0), t('home.sets')],
    [compactNum(data?.unique_cards ?? 0), t('home.unique')],
    [formatPrice(netInvested), t('home.invested')],
  ]
  const sectionTitle = 'font-serif text-lg text-text-primary'
  const linkBtn = 'text-xs text-brand-red hover:text-brand-red-light transition-colors'

  return (
    <div className="min-h-dvh flex flex-col overflow-x-hidden">
      <div className="mx-auto w-full max-w-6xl px-5 pt-5 pb-12 sm:px-8 lg:px-12">

        {/* Top bar */}
        <div className="flex items-center justify-between mb-8 min-h-[44px]">
          <p className="font-serif text-lg truncate">{t('home.hello')}, {trainerName}</p>
          <div className="flex items-center gap-4">
            {user?.role === 'admin' && (
              <button onClick={() => syncMutation.mutate()} disabled={isRunning}
                className="flex items-center gap-1.5 min-h-[44px] text-xs text-text-secondary hover:text-text-primary disabled:opacity-60">
                <RefreshCw size={13} className={isRunning ? 'animate-spin' : ''} />
                {isRunning ? t('home.syncing') : t('home.sync')}
              </button>
            )}
            {multiUser && (
              <button onClick={() => { logout(); navigate('/login') }}
                className="flex items-center gap-1.5 min-h-[44px] text-xs text-text-secondary hover:text-text-primary">
                <LogOut size={13} />{t('auth.logout')}
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-12 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:gap-16">

          {/* ── Left: value, chart, navigation ── */}
          <div className="flex flex-col gap-10 min-w-0">
            <section>
              <div className="flex gap-5 mb-2" role="group" aria-label={t('home.portfolioDisplayMode')}>
                {[
                  ['portfolio_value', t('home.portfolioValue')],
                  ['capital_invested', t('home.capitalInvested')],
                ].map(([mode, label]) => {
                  const selected = portfolioDisplayMode === mode
                  return (
                    <button key={mode} type="button" aria-pressed={selected}
                      onClick={() => setPortfolioDisplayMode(mode)}
                      className={`min-h-[44px] text-sm transition-colors border-b ${selected ? 'text-text-primary border-brand-red' : 'text-text-muted border-transparent hover:text-text-secondary'}`}>
                      {label}
                    </button>
                  )
                })}
                {showingPortfolioValue && productValueExplanation && (
                  <ProductValueInfo label="" detailsLabel={t('home.details')} explanation={productValueExplanation} />
                )}
              </div>
              {isLoading ? (
                <div className="skeleton h-12 w-44 rounded-md" />
              ) : (
                <p className="font-serif font-light text-[40px] leading-[1.15] tracking-tight">{formatPrice(headlineValue)}</p>
              )}
              {!isLoading && (
                <p className="mt-1 text-sm" style={{ color: gain }}>
                  {pnlPositive ? '+' : '−'}{formatPrice(Math.abs(pnl))}
                  {performanceCostBasis > 0 && <span> ({pnlPositive ? '+' : '−'}{Math.abs(pnlPct).toFixed(1)} %)</span>}
                  {(realizedValue > 0 || realizedPnl !== 0) && (
                    <span className="text-text-muted"> · {t('analytics.realizedPnl')} {realizedPnl >= 0 ? '+' : '−'}{formatPrice(Math.abs(realizedPnl))}</span>
                  )}
                </p>
              )}
              <p className="mt-3 text-sm text-text-secondary">
                {stats.map(([v, l], i) => (
                  <span key={l}>{i > 0 && ' · '}{isLoading ? '—' : v} {l.toLowerCase()}</span>
                ))}
              </p>
            </section>

            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className={sectionTitle}>{t('home.portfolioHistory')}</h2>
                <div className="flex gap-1">
                  {PORTFOLIO_PERIODS.map(p => (
                    <button key={p.key} onClick={() => setChartPeriod(p.key)}
                      aria-pressed={chartPeriod === p.key}
                      className={`min-h-[44px] min-w-[36px] px-2 text-xs transition-colors ${chartPeriod === p.key ? 'text-brand-red' : 'text-text-muted hover:text-text-secondary'}`}>
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              {chartData.length < 2 ? (
                <div className="flex flex-col items-start justify-center h-24 gap-1 border-t border-border pt-4">
                  <p className="text-sm text-text-secondary">{t('home.noData')}</p>
                  <p className="text-xs text-text-muted">{t('home.startSyncHint')}</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={130}>
                  <AreaChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                    <XAxis dataKey="date" tick={{ fill: '#8A877F', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                    <YAxis hide domain={['auto', 'auto']} />
                    <Tooltip content={<ChartTooltip formatPrice={formatPrice} />} cursor={{ stroke: 'rgba(228,225,218,0.15)', strokeWidth: 1 }} />
                    <Area type="monotone" dataKey="value" stroke={chartColor} strokeWidth={1.5} fill="none" dot={false}
                      activeDot={{ r: 3, fill: chartColor, stroke: 'none' }} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </section>

            {Number(data?.price_choice_count ?? 0) > 0 && (
              <section>
                <h2 className={`${sectionTitle} mb-1`}>{t('home.priceChoices')}</h2>
                <p className="text-xs text-text-muted mb-1">
                  {t('home.priceChoicesHint').replace('{count}', data.price_choice_count)}
                </p>
                {(data.price_choices || []).map(choice => (
                  <button key={choice.collection_item_id} onClick={() => openCollectionItem(choice)}
                    className="flex w-full items-center justify-between gap-3 min-h-[56px] border-b border-border text-left">
                    <span className="min-w-0">
                      <span className="block text-sm truncate">{choice.name}</span>
                      <span className="block text-xs text-text-muted">
                        Cardmarket {formatPrice(choice.cardmarket ?? 0)} · TCGPlayer {formatPrice(choice.tcgplayer ?? 0)}
                      </span>
                    </span>
                    <span className="text-xs text-brand-red">{t('home.priceChoiceAction')}</span>
                  </button>
                ))}
              </section>
            )}

            <section>
              <h2 className={`${sectionTitle} mb-1`}>{t('home.navigation')}</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 sm:gap-x-10">
                {PORTAL_ITEMS.map(({ to, icon: Icon, label, badge, active }) => (
                  <button key={to} onClick={() => navigate(to)}
                    className="flex items-center gap-3 min-h-[48px] border-b border-border text-sm text-text-primary hover:text-brand-red transition-colors text-left">
                    <Icon size={16} className="text-text-muted" aria-hidden="true" />
                    <span className="flex-1">{label}</span>
                    {badge > 0 && <span className="text-xs text-brand-red">{badge > 99 ? '99+' : badge}</span>}
                    {!badge && active && <span className="h-2 w-2 animate-pulse rounded-full bg-brand-red" aria-hidden="true" />}
                  </button>
                ))}
              </div>
            </section>
          </div>

          {/* ── Right: cards ── */}
          <div className="flex flex-col gap-10 min-w-0">
            {(recentCards.length > 0 || topCards.length > 0) && (
              <CardLegend legendProps={{ showWishlist: false }} />
            )}

            {recentCards.length > 0 && (
              <section>
                <div className="flex items-baseline justify-between mb-3">
                  <h2 className={sectionTitle}>{t('home.recentlyAdded')}</h2>
                  <button onClick={() => navigate('/collection')} className={linkBtn}>{t('home.viewAll')}</button>
                </div>
                <div className="flex gap-3 overflow-x-auto pb-1 no-scrollbar -mx-5 px-5 sm:-mx-8 sm:px-8 lg:mx-0 lg:px-0">
                  {recentCards.map(card => (
                    <CardThumb key={card.id} card={card} onClick={() => openCollectionItem(card)} />
                  ))}
                </div>
              </section>
            )}

            {topCards.length > 0 && (
              <section>
                <div className="flex items-baseline justify-between mb-3">
                  <h2 className={sectionTitle}>{t('home.topCards')}</h2>
                  <button onClick={() => navigate('/analytics')} className={linkBtn}>{t('home.details')}</button>
                </div>
                <div className="flex gap-3 overflow-x-auto pb-1 no-scrollbar -mx-5 px-5 sm:-mx-8 sm:px-8 lg:mx-0 lg:px-0">
                  {topCards.map(card => (
                    <div key={card.collection_item_id || card.id} className="flex-shrink-0 w-[110px] cursor-pointer"
                      onClick={() => openCollectionItem(card)}>
                      <CollectionCardDisplay
                        variant="artwork"
                        item={{ id: card.collection_item_id, has_scan_photo: card.has_scan_photo }}
                        card={card}
                        alt={card.name}
                        variantEffectSource={card.variant}
                        stateIndicatorProps={{ card: withCollectionItemState(card, card), alwaysShowQuantity: true }}
                      />
                      <p className="text-xs mt-1.5 text-text-secondary">{formatPrice(Number(card.total_value ?? 0))}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
