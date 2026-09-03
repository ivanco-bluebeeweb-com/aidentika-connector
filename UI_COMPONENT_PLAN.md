# Aidentika — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на функционале `aidentika-connector`.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(sparks balance) + `ui.Divider` + navigation `ui.ListItem`(Projects/Generations/Webhooks) + `ui.Button`("App settings") | Без карточек по стандарту; баланс sparks как контекстная метка сверху (платный usage-based сервис). |
| Project List (center, `center_overlay=True`) | `ui.DataTable`(name, product name, category, cards count; sortable) + `ui.Button`("Создать проект") | Табличный обзор проектов-контейнеров для карточек генерации. |
| Project Detail (Cards) | Back-button + `ui.DataTable`(image thumb via `ui.Image` в ячейке, status Badge pending/processing/completed, concept, created; sortable) | Карточки проекта — визуальный контент, превью в ячейке критично для быстрой навигации. |
| Generate Product Photo Form | `ui.Form`(action="generate_product_photo") + `ui.FileUpload`(accept="image/*", multiple=True, до 5 референсных фото) + `ui.Select`(category/concept) + `ui.TextArea`(comment) + `ui.Button`("Сгенерировать") | `FileUpload` с multiple — прямое соответствие лимиту 1-5 референсных изображений. |
| Generation Result Viewer | Back-button + `ui.Image`(результат крупно) + `ui.KeyValue`(status/sparks cost/created) + `ui.Row`(Button "Скачать", "Улучшить/Edit", "Анимировать в видео") | Прямой просмотр результата с действиями по цепочке (edit/video из готового фото). |
| Video Generation Form | `ui.Form`(action="generate_product_video") + выбор исходного изображения (через клик из Generation Result Viewer, передаётся как параметр) + `ui.Select`(duration, options=[5,10]) + `ui.TextArea`(scenario) | Анимация уже существующего сгенерированного фото — форма получает image reference из предыдущего экрана. |
| Generation Queue/History | `ui.Select`(type_filter: photo/card/video) + `ui.DataTable`(type Badge, status Badge pending/processing/completed/failed, created; sortable) | Табличная история всех генераций с фильтром по типу. |
| Balance & Pricing | `ui.Stats`(Available sparks/Held sparks) + `ui.DataTable`(operation, sparks cost; sortable) | Прозрачная сводка баланса и прайсинга операций. |
| Webhook Manager | `ui.List`(webhooks: url, events) + `ui.Button`("Добавить webhook") | Простой список зарегистрированных вебхуков. |
| App Settings | `ui.Accordion`([Connections+Disconnect, API Key Config]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__aidentika_sidebar` рендерит баланс sparks + разделы,
   `auto_action` открывает Project List.
2. Клик на проект → Project Detail (Cards) — таблица с превью.
3. "Создать проект" / "Сгенерировать" → Generate Product Photo Form → загрузка фото
   → `ui.Call("generate_product_photo")` → переход в Generation Queue (статус pending).
4. Клик на завершённую генерацию → Generation Result Viewer — крупное превью +
   действия "Улучшить"/"Анимировать".
5. "Анимировать в видео" → Video Generation Form с уже подставленным image_id →
   `ui.Call("generate_product_video")`.
6. Balance & Pricing и Webhook Manager — отдельные пункты сайдбара, read-only/CRUD.
7. App Settings — только через кнопку в сайдбаре, единственное место с disconnect.

## 3. Экраны/карточки (артефакты для реализации)

- `panels.py`: `__panel__aidentika_sidebar` (left).
- `panels_projects.py`: `__panel__project_list` (center, `center_overlay=True`),
  `__panel__project_detail` (center, параметризован `project_id`).
- `panels_generation.py`: `__panel__generate_photo_form` (center overlay),
  `__panel__generation_result` (center, параметризован `action_id`),
  `__panel__generate_video_form` (center overlay, параметризован `image_id`),
  `__panel__generation_queue` (center).
- `panels_billing.py`: `__panel__balance_pricing` (center).
- `panels_webhooks.py`: `__panel__webhook_manager` (center).
- `panels_settings.py`: `__panel__app_settings` (center overlay, Accordion,
  единственное место с disconnect).
