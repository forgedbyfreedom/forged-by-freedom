/**
 * Hooks that can be added to wix-data operations.
 * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#)
 */
declare module 'DataHooks' {
    import wixData from 'wix-data';
    /**
     * A hook triggered after an aggregation operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterAggregate)
     */
    function afterAggregate(item: any, context: HookContext): Promise<any> & any;
    /**
     * A hook that is triggered after a `count()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterCount)
     */
    function afterCount(count: number, context: HookContext): Promise<number> & number;
    /**
     * A hook that is triggered after a `get()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterGet)
     */
    function afterGet(item: any, context: HookContext): Promise<any> & any;
    /**
     * A hook that is triggered after an `insert()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterInsert)
     */
    function afterInsert(item: any, context: HookContext): Promise<any> & any;
    /**
     * A hook that is triggered after a `find` operation, for each of the items in the query results.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterQuery)
     */
    function afterQuery(item: any, context: HookContext): Promise<any> & any;
    /**
     * A hook that is triggered after a `remove()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterRemove)
     */
    function afterRemove(item: any, context: HookContext): Promise<any> & any;
    /**
     * A hook that is triggered after an `update()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#afterUpdate)
     */
    function afterUpdate(item: any, context: UpdateHookContext): Promise<any> & any;
    /**
     * A hook that is triggered before a `count()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#beforeCount)
     */
    function beforeCount(query: wixData.WixDataQuery, context: HookContext): Promise<wixData.WixDataQuery> & wixData.WixDataQuery;
    /**
     * A hook that is triggered before a `get()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#beforeGet)
     */
    function beforeGet(itemId: string, context: HookContext): Promise<string> & string;
    /**
     * A hook that is triggered before an `insert()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#beforeInsert)
     */
    function beforeInsert(item: any, context: HookContext): Promise<any> & any;
    /**
     * A hook that is triggered before a `find()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#beforeQuery)
     */
    function beforeQuery(query: wixData.WixDataQuery, context: HookContext): Promise<wixData.WixDataQuery> & wixData.WixDataQuery;
    /**
     * A hook that is called before a `remove()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#beforeRemove)
     */
    function beforeRemove(itemId: string, context: UpdateHookContext): Promise<string> & string;
    /**
     * A hook that is triggered before an `update()` operation.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#beforeUpdate)
     */
    function beforeUpdate(item: any, context: UpdateHookContext): Promise<any> & any;
    /**
     * A hook that is triggered on any error or rejected Promise from any of the wix-data operations.
     * 	[Read more](https://www.wix.com/corvid/reference/DataHooks.html#onFailure)
     */
    function onFailure(error: Error, context: HookContext): Promise<any>;
    /**
     * An object that contains contextual information about the hook being called.
     */
    type HookContext = {
        /**
         * The ID of the collection the hook affects.
         */
        collectionName: string;
        /**
         * The current site user ID. If no user is logged in to the site it may be null.
         */
        userId: string;
        /**
         * The permissions role of the current user. Possibilities are: `anonymous`, `siteMember`, and `siteOwner`.
         */
        userRole: string;
    };
    /**
     * An object that contains contextual information when calling the `beforeUpdate()`, `beforeRemove()`, or `afterUpdate()` hooks.
     */
    type UpdateHookContext = {
        /**
         * The ID of the collection the hook affects.
         */
        collectionName: string;
        /**
         * The current site user ID. If no user is logged in to the site it may be null.
         */
        userId: string;
        /**
         * The permissions role of the current user. Possibilities are: `anonymous`, `siteMember`, and `siteOwner`.
         */
        userRole: string;
        /**
         * The item stored in the database collection before an update or delete operation.
         */
        currentItem: any;
    };
}
