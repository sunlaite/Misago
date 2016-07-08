from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from misago.acl import add_acl
from misago.categories.models import Category
from misago.categories.permissions import allow_browse_category, allow_see_category
from misago.categories.serializers import CategorySerializer
from misago.core.apipatch import ApiPatch
from misago.core.shortcuts import get_int_or_404, get_object_or_404

from ...moderation import threads as moderation
from ...permissions import allow_start_thread
from ...utils import add_categories_to_threads


thread_patch_endpoint = ApiPatch()


def patch_weight(request, thread, value):
    message = _("You don't have permission to change this thread's weight.")
    if not thread.acl.get('can_pin'):
        raise PermissionDenied(message)
    elif thread.weight > thread.acl.get('can_pin'):
        raise PermissionDenied(message)

    if value == 2:
        if thread.acl.get('can_pin') == 2:
            moderation.pin_thread_globally(request, thread)
        else:
            raise PermissionDenied(
                _("You don't have permission to pin this thread globally."))
    elif value == 1:
        moderation.pin_thread_locally(request, thread)
    elif value == 0:
        moderation.unpin_thread(request, thread)

    return {'weight': thread.weight}
thread_patch_endpoint.replace('weight', patch_weight)


def patch_move(request, thread, value):
    if thread.acl.get('can_move'):
        category_pk = get_int_or_404(value)
        new_category = get_object_or_404(
            Category.objects.all_categories().select_related('parent'),
            pk=category_pk
        )

        add_acl(request.user, new_category)
        allow_see_category(request.user, new_category)
        allow_browse_category(request.user, new_category)
        allow_start_thread(request.user, new_category)

        moderation.move_thread(request, thread, new_category)

        return {'category': CategorySerializer(new_category).data}
    else:
        raise PermissionDenied(
            _("You don't have permission to move this thread."))
thread_patch_endpoint.replace('category', patch_move)


def patch_top_category(request, thread, value):
    category_pk = get_int_or_404(value)
    root_category = get_object_or_404(
        Category.objects.all_categories(include_root=True),
        pk=category_pk
    )

    categories = list(Category.objects.all_categories().filter(
        id__in=request.user.acl['visible_categories']
    ))
    add_categories_to_threads(root_category, categories, [thread])
    return {'top_category': CategorySerializer(thread.top_category).data}
thread_patch_endpoint.add('top-category', patch_top_category)


def patch_flatten_categories(request, thread, value):
    try:
        return {
            'category': thread.category_id,
            'top_category': thread.top_category.pk,
        }
    except AttributeError as e:
        return {
            'category': thread.category_id,
            'top_category': None
        }
thread_patch_endpoint.replace('flatten-categories', patch_flatten_categories)


def patch_is_unapproved(request, thread, value):
    if thread.acl.get('can_approve'):
        if value:
            raise PermissionDenied(_("Content approval can't be reversed."))

        moderation.approve_thread(request, thread)

        return {
            'is_unapproved': thread.is_unapproved,
            'has_unapproved_posts': thread.has_unapproved_posts,
        }
    else:
        raise PermissionDenied(
            _("You don't have permission to approve this thread."))
thread_patch_endpoint.replace('is-unapproved', patch_is_unapproved)


def patch_is_closed(request, thread, value):
    if thread.acl.get('can_close'):
        if value:
            moderation.close_thread(request, thread)
        else:
            moderation.open_thread(request, thread)

        return {'is_closed': thread.is_closed}
    else:
        if value:
            raise PermissionDenied(
                _("You don't have permission to close this thread."))
        else:
            raise PermissionDenied(
                _("You don't have permission to open this thread."))
thread_patch_endpoint.replace('is-closed', patch_is_closed)


def patch_is_hidden(request, thread, value):
    if thread.acl.get('can_hide'):
        if value:
            moderation.hide_thread(request, thread)
        else:
            moderation.unhide_thread(request, thread)

        return {'is_hidden': thread.is_hidden}
    else:
        raise PermissionDenied(
            _("You don't have permission to hide this thread."))
thread_patch_endpoint.replace('is-hidden', patch_is_hidden)


def patch_subscribtion(request, thread, value):
    request.user.subscription_set.filter(thread=thread).delete()

    if value == 'notify':
        thread.subscription = request.user.subscription_set.create(
            thread=thread,
            category=thread.category,
            last_read_on=thread.last_post_on,
            send_email=False,
        )

        return {'subscription': False}
    elif value == 'email':
        thread.subscription = request.user.subscription_set.create(
            thread=thread,
            category=thread.category,
            last_read_on=thread.last_post_on,
            send_email=True,
        )

        return {'subscription': True}
    else:
        return {'subscription': None}
thread_patch_endpoint.replace('subscription', patch_subscribtion)
