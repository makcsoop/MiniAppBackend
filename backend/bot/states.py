from aiogram.fsm.state import State, StatesGroup


class CategoryForm(StatesGroup):
    name = State()
    slug = State()
    description = State()
    icon_url = State()
    sort_order = State()


class ProductForm(StatesGroup):
    title = State()
    slug = State()
    description = State()
    price = State()
    currency = State()
    product_type = State()
    status = State()
    category_id = State()
    image_url = State()
    is_featured = State()
    sort_order = State()


class UserSearchForm(StatesGroup):
    query = State()
